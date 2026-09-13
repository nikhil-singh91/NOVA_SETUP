"""Groq provider implementation for NOVA.

This module implements :class:`GroqProvider`, the concrete
:class:`~providers.base_provider.BaseProvider` subclass that connects
NOVA to Groq's low-latency inference API via the official ``groq``
Python SDK.

This module contains only Groq-specific mechanics: constructing and
tearing down the ``groq.Groq`` client, translating chat-completion
requests into the base class's abstract hooks, and translating Groq
SDK exceptions into :class:`~core.exceptions.GroqError`. Logging,
timing, common argument validation, and lifecycle state tracking are
all handled once, in :class:`~providers.base_provider.BaseProvider`,
and are intentionally not duplicated here.

The Groq API key is never read from an environment variable directly
in this module; it is obtained exclusively through
``config.settings.settings``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, Final

from groq import APIConnectionError, APIStatusError, Groq, RateLimitError
from groq.types.chat import ChatCompletionMessageParam

from config.settings import settings
from core.exceptions import GroqError
from core.logger import get_logger
from providers.base_provider import BaseProvider

logger = get_logger(__name__)

# The default Groq model used for chat completions. This is a
# non-secret identifier and is intentionally defined here, local to
# the Groq provider, rather than in application configuration.
_DEFAULT_MODEL: Final[str] = "groq/compound-mini"

# The system role label used when constructing chat messages, per the
# Groq chat-completions message format.
_ROLE_SYSTEM: Final[str] = "system"
_ROLE_USER: Final[str] = "user"

# A minimal, low-cost message used solely to verify connectivity
# during health checks; it is never surfaced to end users.
_HEALTH_CHECK_PROMPT: Final[str] = "ping"

# A rough characters-per-token ratio used to estimate token counts in
# the absence of an official Groq tokenizer exposed through the SDK.
# This is an approximation only, intentionally conservative, and
# should be replaced with an exact tokenizer if Groq exposes one in
# the future.
_APPROXIMATE_CHARACTERS_PER_TOKEN: Final[int] = 4


class GroqProvider(BaseProvider):
    """AI provider backed by Groq, via the official ``groq`` SDK.

    Attributes:
        _client: The underlying ``groq.Groq`` client instance, or
            ``None`` if the provider has not been initialized.
        _model: The Groq model identifier used for all requests
            issued by this provider instance.
    """

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize a Groq provider instance.

        Args:
            model: The Groq model identifier to use for all requests.
                Defaults to :data:`_DEFAULT_MODEL`.
        """
        super().__init__()
        self._client: Groq | None = None
        self._model: str = model

    # -------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Return the unique name of this provider.

        Returns:
            The literal string ``"groq"``.
        """
        return "groq"

    # -------------------------------------------------------------------
    # Capabilities
    # -------------------------------------------------------------------

    def supports_streaming(self) -> bool:
        """Report that Groq supports streaming responses.

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
        """Report that Groq supports structured function calling.

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
        """Construct the underlying Groq client.

        The client is constructed exactly once per provider instance;
        idempotency across repeated calls to
        :meth:`~providers.base_provider.BaseProvider.initialize` is
        already enforced by the base class.

        Raises:
            GroqError: If the Groq API key is missing or the client
                fails to construct.
        """
        api_key = settings.groq_api_key.get_secret_value()
        if not api_key.strip():
            raise GroqError("Cannot initialize Groq provider: API key is empty.")

        try:
            self._client = Groq(api_key=api_key)
        except Exception as exc:
            raise GroqError(
                "Failed to construct the Groq client.", original_exception=exc
            ) from exc

    def _do_shutdown(self) -> None:
        """Release the underlying Groq client by clearing the reference.

        The ``groq.Groq`` client does not require explicit closing of
        network resources beyond normal garbage collection, so
        shutdown here simply releases NOVA's reference to it.
        """
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
        """Generate a complete response using the Groq chat completions API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Returns:
            The generated response text.

        Raises:
            GroqError: If the underlying client is not initialized,
                or if the Groq API request fails.
        """
        self._ensure_client_ready()
        messages = self._build_messages(prompt, system_prompt)

        try:
            extra_kwargs: dict[str, Any] = {}
            if "qwen" in self._model.lower() or "deepseek" in self._model.lower():
                extra_kwargs["extra_body"] = {"reasoning_format": "hidden"}
                if max_tokens is not None and max_tokens < 700:
                    max_tokens = 700

            completion = self._client.chat.completions.create(  # type: ignore[union-attr]
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                stream=False,
                **extra_kwargs,
            )
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
            raise GroqError(f"Groq API request failed: {exc}", original_exception=exc) from exc
        except Exception as exc:
            raise GroqError(
                "An unexpected error occurred during Groq generation.",
                original_exception=exc,
            ) from exc

        content = completion.choices[0].message.content
        if not content:
            raise GroqError("Groq returned an empty response.")

        return content

    def _do_stream_response(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> Iterator[str]:
        """Generate a streaming response using the Groq chat completions API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Yields:
            Successive text chunks of the generated response.

        Raises:
            GroqError: If the underlying client is not initialized,
                or if the Groq API request fails.
        """
        self._ensure_client_ready()
        messages = self._build_messages(prompt, system_prompt)

        try:
            stream = self._client.chat.completions.create(  # type: ignore[union-attr]
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=max_tokens,
                stream=True,
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
            raise GroqError(
                f"Groq API streaming request failed: {exc}", original_exception=exc
            ) from exc
        except Exception as exc:
            raise GroqError(
                "An unexpected error occurred during Groq streaming.",
                original_exception=exc,
            ) from exc

    # -------------------------------------------------------------------
    # Diagnostics hooks
    # -------------------------------------------------------------------

    def _do_count_tokens(self, text: str) -> int:
        """Estimate the number of tokens Groq would use for the given text.

        The Groq SDK does not currently expose an official tokenizer,
        so this provides a reasonable approximation based on average
        English text density, rather than an exact count.

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
        """Verify that the Groq client is initialized and reachable.

        Issues a minimal chat completion request with a very small
        token budget, which confirms both authentication and
        connectivity at negligible cost.

        Returns:
            ``True`` if the health check succeeds, ``False`` otherwise.
        """
        if self._client is None:
            raise GroqError("Groq provider is not initialized: API key missing or unconfigured.")

        health_messages: list[ChatCompletionMessageParam] = [
            {"role": "user", "content": _HEALTH_CHECK_PROMPT}
        ]
        self._client.chat.completions.create(
            model=self._model,
            messages=health_messages,
            max_completion_tokens=1,
            stream=False,
        )
        return True

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _ensure_client_ready(self) -> None:
        """Verify the Groq client is initialized before issuing a request.

        Raises:
            GroqError: If :meth:`initialize` has not been called
                successfully, or the client is otherwise unavailable.
        """
        if not self.is_available or self._client is None:
            raise GroqError(
                "Groq provider is not initialized. Call initialize() before "
                "issuing requests."
            )

    def _build_messages(
        self, prompt: str, system_prompt: str | None
    ) -> list[ChatCompletionMessageParam]:
        """Build the chat message list for a Groq chat completions request.

        Args:
            prompt: The user-facing prompt.
            system_prompt: An optional system-level instruction.

        Returns:
            A list of chat messages in the Groq/OpenAI-compatible
            message format.
        """
        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return messages


__all__ = [
    "GroqProvider",
]
