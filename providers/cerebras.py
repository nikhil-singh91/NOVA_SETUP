"""Cerebras provider implementation for NOVA.

This module implements :class:`CerebrasProvider`, the concrete
:class:`~providers.base_provider.BaseProvider` subclass that connects
NOVA to Cerebras's high-throughput inference API via the official
``cerebras-cloud-sdk`` Python package.

This module contains only Cerebras-specific mechanics: constructing
and tearing down the ``cerebras.cloud.sdk.Cerebras`` client,
translating chat-completion requests into the base class's abstract
hooks, and translating Cerebras SDK exceptions into
:class:`~core.exceptions.CerebrasError`. Logging, timing, common
argument validation, and lifecycle state tracking are all handled
once, in :class:`~providers.base_provider.BaseProvider`, and are
intentionally not duplicated here.

The Cerebras API key is never read from an environment variable
directly in this module; it is obtained exclusively through
``config.settings.settings``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final

from cerebras.cloud.sdk import APIConnectionError, APIStatusError, Cerebras, RateLimitError
from config.settings import settings
from core.exceptions import CerebrasError
from core.logger import get_logger
from providers.base_provider import BaseProvider

logger = get_logger(__name__)

# The default Cerebras model used for chat completions. This is a
# non-secret identifier and is intentionally defined here, local to
# the Cerebras provider, rather than in application configuration.
_DEFAULT_MODEL: Final[str] = "qwen-3.8-27b"

_ROLE_SYSTEM: Final[str] = "system"
_ROLE_USER: Final[str] = "user"

# A minimal, low-cost message used solely to verify connectivity
# during health checks; it is never surfaced to end users.
_HEALTH_CHECK_PROMPT: Final[str] = "ping"

# A rough characters-per-token ratio used to estimate token counts in
# the absence of an official Cerebras tokenizer exposed through the
# SDK. This is an approximation only, intentionally conservative, and
# should be replaced with an exact tokenizer if Cerebras exposes one
# in the future.
_APPROXIMATE_CHARACTERS_PER_TOKEN: Final[int] = 4


class CerebrasProvider(BaseProvider):
    """AI provider backed by Cerebras, via the official ``cerebras-cloud-sdk``.

    Attributes:
        _client: The underlying ``cerebras.cloud.sdk.Cerebras`` client
            instance, or ``None`` if the provider has not been
            initialized.
        _model: The Cerebras model identifier used for all requests
            issued by this provider instance.
    """

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize a Cerebras provider instance.

        Args:
            model: The Cerebras model identifier to use for all
                requests. Defaults to :data:`_DEFAULT_MODEL`.
        """
        super().__init__()
        self._client: Cerebras | None = None
        self._model: str = model

    # -------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Return the unique name of this provider.

        Returns:
            The literal string ``"cerebras"``.
        """
        return "cerebras"

    # -------------------------------------------------------------------
    # Capabilities
    # -------------------------------------------------------------------

    def supports_streaming(self) -> bool:
        """Report that Cerebras supports streaming responses.

        Returns:
            ``True``.
        """
        return True

    def supports_vision(self) -> bool:
        """Report that this provider does not implement vision input.

        Returns:
            ``False``.
        """
        return False

    def supports_tools(self) -> bool:
        """Report that this provider does not implement tool use.

        Returns:
            ``False``.
        """
        return False

    def supports_function_calling(self) -> bool:
        """Report that Cerebras supports structured function calling.

        Returns:
            ``True``.
        """
        return True

    def supports_embeddings(self) -> bool:
        """Report that this provider does not implement embeddings.

        Returns:
            ``False``.
        """
        return False

    def supports_audio(self) -> bool:
        """Report that this provider does not implement audio input.

        Returns:
            ``False``.
        """
        return False

    def supports_images(self) -> bool:
        """Report that this provider does not implement image generation.

        Returns:
            ``False``.
        """
        return False

    # -------------------------------------------------------------------
    # Lifecycle hooks
    # -------------------------------------------------------------------

    def _do_initialize(self) -> None:
        """Construct the underlying Cerebras client.

        The client is constructed exactly once per provider instance;
        idempotency across repeated calls to
        :meth:`~providers.base_provider.BaseProvider.initialize` is
        already enforced by the base class.

        Raises:
            CerebrasError: If the Cerebras API key is missing or the
                client fails to construct.
        """
        api_key = settings.cerebras_api_key.get_secret_value()
        if not api_key.strip():
            raise CerebrasError("Cannot initialize Cerebras provider: API key is empty.")

        try:
            self._client = Cerebras(api_key=api_key)
        except Exception as exc:
            raise CerebrasError(
                "Failed to construct the Cerebras client.", original_exception=exc
            ) from exc

        logger.info("[cerebras] Client constructed for model '%s'.", self._model)

    def _do_shutdown(self) -> None:
         """Release the underlying Cerebras client."""
         self._client = None

    # -------------------------------------------------------------------
    # Generation hooks
    # -------------------------------------------------------------------

    def _do_generate_response(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> str:
        """Generate a complete response using the Cerebras chat completions API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Returns:
            The generated response text.

        Raises:
            CerebrasError: If the underlying client is not
                initialized, or if the Cerebras API request fails.
        """
        self._ensure_client_ready()
        messages = self._build_messages(prompt, system_prompt)

        logger.debug(
            "[cerebras] Sending generation request (model=%s, temperature=%s, "
            "max_tokens=%s).",
            self._model,
            temperature,
            max_tokens,
        )
        try:
            completion = self._client.chat.completions.create(  # type: ignore[union-attr]
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
            raise CerebrasError(
                f"Cerebras API request failed: {exc}", original_exception=exc
            ) from exc
        except Exception as exc:
            raise CerebrasError(
                "An unexpected error occurred during Cerebras generation.",
                original_exception=exc,
            ) from exc

        content = completion.choices[0].message.content
        if not content:
            raise CerebrasError("Cerebras returned an empty response.")

        logger.info("[cerebras] Generation request completed successfully.")
        return content

    def _do_stream_response(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> Iterator[str]:
        """Generate a streaming response using the Cerebras chat completions API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Yields:
            Successive text chunks of the generated response.

        Raises:
            CerebrasError: If the underlying client is not
                initialized, or if the Cerebras API request fails.
        """
        self._ensure_client_ready()
        messages = self._build_messages(prompt, system_prompt)

        logger.debug(
            "[cerebras] Sending streaming request (model=%s, temperature=%s, "
            "max_tokens=%s).",
            self._model,
            temperature,
            max_tokens,
        )
        try:
            stream = self._client.chat.completions.create(  # type: ignore[union-attr]
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
            raise CerebrasError(
                f"Cerebras API streaming request failed: {exc}", original_exception=exc
            ) from exc
        except Exception as exc:
            raise CerebrasError(
                "An unexpected error occurred during Cerebras streaming.",
                original_exception=exc,
            ) from exc
        else:
            logger.info("[cerebras] Streaming request completed successfully.")

    # -------------------------------------------------------------------
    # Diagnostics hooks
    # -------------------------------------------------------------------

    def _do_count_tokens(self, text: str) -> int:
        """Estimate the number of tokens Cerebras would use for the given text.

        The Cerebras SDK does not currently expose an official
        tokenizer, so this provides a reasonable approximation based
        on average English text density, rather than an exact count.

        Args:
            text: The text to estimate a token count for.

        Returns:
            An estimated token count. Always at least ``1`` for
            non-empty text.
        """
        if not text:
            return 0
        return max(1, len(text) // _APPROXIMATE_CHARACTERS_PER_TOKEN)

    def _do_health_check(self) -> bool:
        """Verify that the Cerebras client is initialized and reachable.

        Issues a minimal chat completion request with a very small
        token budget, which confirms both authentication and
        connectivity at negligible cost.

        Returns:
            ``True`` if the health check succeeds, ``False`` otherwise.
        """
        if self._client is None:
            raise CerebrasError("Cerebras provider is not initialized: API key missing or unconfigured.")

        self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": _ROLE_USER, "content": _HEALTH_CHECK_PROMPT}],
            max_tokens=1,
            stream=False,
        )
        logger.debug("[cerebras] Health check succeeded.")
        return True

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _ensure_client_ready(self) -> None:
        """Verify the Cerebras client is initialized before issuing a request.

        Raises:
            CerebrasError: If :meth:`initialize` has not been called
                successfully, or the client is otherwise unavailable.
        """
        if not self.is_available or self._client is None:
            raise CerebrasError(
                "Cerebras provider is not initialized. Call initialize() before "
                "issuing requests."
            )

    def _build_messages(
        self, prompt: str, system_prompt: str | None
    ) -> list[dict[str, str]]:
        """Build the chat message list for a Cerebras chat completions request.

        Args:
            prompt: The user-facing prompt.
            system_prompt: An optional system-level instruction.

        Returns:
            A list of chat messages in the OpenAI-compatible message
            format used by Cerebras.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": _ROLE_SYSTEM, "content": system_prompt})
        messages.append({"role": _ROLE_USER, "content": prompt})
        return messages


__all__ = [
    "CerebrasProvider",
]
