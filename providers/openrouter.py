"""OpenRouter provider implementation for NOVA.

This module implements :class:`OpenRouterProvider`, the concrete
:class:`~providers.base_provider.BaseProvider` subclass that connects
NOVA to OpenRouter's unified model gateway. OpenRouter exposes an
OpenAI-compatible REST API, so this provider uses the official
``openai`` Python SDK configured with OpenRouter's base URL, rather
than a separate OpenRouter-specific client library.

This module contains only OpenRouter-specific mechanics: constructing
and tearing down the ``openai.OpenAI`` client pointed at OpenRouter,
translating chat-completion requests into the base class's abstract
hooks, and translating OpenAI SDK exceptions into
:class:`~core.exceptions.OpenRouterError`. Logging, timing, common
argument validation, and lifecycle state tracking are all handled
once, in :class:`~providers.base_provider.BaseProvider`, and are
intentionally not duplicated here.

The OpenRouter API key is never read from an environment variable
directly in this module; it is obtained exclusively through
``config.settings.settings``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from config.settings import settings
from core.exceptions import OpenRouterError
from core.logger import get_logger
from providers.base_provider import BaseProvider

logger = get_logger(__name__)

# OpenRouter's OpenAI-compatible API endpoint. This is a fixed,
# non-secret service address and is intentionally defined here,
# local to the OpenRouter provider, rather than in application
# configuration.
_OPENROUTER_BASE_URL: Final[str] = "https://openrouter.ai/api/v1"

# The default OpenRouter model slug used for chat completions. This is
# a non-secret identifier and is intentionally defined here, local to
# the OpenRouter provider, rather than in application configuration.
_DEFAULT_MODEL: Final[str] = "openai/gpt-4o-mini"

_ROLE_SYSTEM: Final[str] = "system"
_ROLE_USER: Final[str] = "user"

# A minimal, low-cost message used solely to verify connectivity
# during health checks; it is never surfaced to end users.
_HEALTH_CHECK_PROMPT: Final[str] = "ping"

# A rough characters-per-token ratio used to estimate token counts in
# the absence of an official tokenizer call for the specific model
# OpenRouter routes a request to. This is an approximation only.
_APPROXIMATE_CHARACTERS_PER_TOKEN: Final[int] = 4


class OpenRouterProvider(BaseProvider):
    """AI provider backed by OpenRouter, via the OpenAI-compatible SDK.

    Attributes:
        _client: The underlying ``openai.OpenAI`` client instance,
            configured with OpenRouter's base URL, or ``None`` if the
            provider has not been initialized.
        _model: The OpenRouter model slug used for all requests
            issued by this provider instance.
    """

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize an OpenRouter provider instance.

        Args:
            model: The OpenRouter model slug to use for all requests
                (for example, ``"openai/gpt-4o-mini"``). Defaults to
                :data:`_DEFAULT_MODEL`.
        """
        super().__init__()
        self._client: OpenAI | None = None
        self._model: str = model

    # -------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Return the unique name of this provider.

        Returns:
            The literal string ``"openrouter"``.
        """
        return "openrouter"

    # -------------------------------------------------------------------
    # Capabilities
    # -------------------------------------------------------------------

    def supports_streaming(self) -> bool:
        """Report that OpenRouter supports streaming responses.

        Returns:
            ``True``.
        """
        return True

    def supports_vision(self) -> bool:
        """Report that OpenRouter supports image understanding.

        Returns:
            ``True``, since OpenRouter routes to models with vision
            capability (for example, ``openai/gpt-4o-mini``).
        """
        return True

    def supports_tools(self) -> bool:
        """Report that OpenRouter supports tool use.

        Returns:
            ``True``.
        """
        return True

    def supports_function_calling(self) -> bool:
        """Report that OpenRouter supports structured function calling.

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
        """Report that OpenRouter supports image generation.

        Returns:
            ``True``, since OpenRouter routes to models capable of
            generating images.
        """
        return False

    # -------------------------------------------------------------------
    # Lifecycle hooks
    # -------------------------------------------------------------------

    def _do_initialize(self) -> None:
        """Construct the underlying OpenAI client, configured for OpenRouter.

        The client is constructed exactly once per provider instance;
        idempotency across repeated calls to
        :meth:`~providers.base_provider.BaseProvider.initialize` is
        already enforced by the base class.

        Raises:
            OpenRouterError: If the OpenRouter API key is missing or
                the client fails to construct.
        """
        api_key = settings.openrouter_api_key.get_secret_value()
        if not api_key.strip():
            raise OpenRouterError(
                "Cannot initialize OpenRouter provider: API key is empty."
            )

        try:
            self._client = OpenAI(base_url=_OPENROUTER_BASE_URL, api_key=api_key)
        except Exception as exc:
            raise OpenRouterError(
                "Failed to construct the OpenRouter client.", original_exception=exc
            ) from exc

    def _do_shutdown(self) -> None:
        """Release the underlying OpenRouter client."""
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
        """Generate a complete response using the OpenRouter chat completions API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Returns:
            The generated response text.

        Raises:
            OpenRouterError: If the underlying client is not
                initialized, or if the OpenRouter API request fails.
        """
        self._ensure_client_ready()
        messages = self._build_messages(prompt, system_prompt)

        try:
            completion = self._client.chat.completions.create(  # type: ignore[union-attr]
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=False,
            )
        except (APIConnectionError, RateLimitError, APIStatusError) as exc:
            raise OpenRouterError(
                f"OpenRouter API request failed: {exc}", original_exception=exc
            ) from exc
        except Exception as exc:
            raise OpenRouterError(
                "An unexpected error occurred during OpenRouter generation.",
                original_exception=exc,
            ) from exc

        content = completion.choices[0].message.content
        if not content:
            raise OpenRouterError("OpenRouter returned an empty response.")

        return content

    def _do_stream_response(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> Iterator[str]:
        """Generate a streaming response using the OpenRouter chat completions API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Yields:
            Successive text chunks of the generated response.

        Raises:
            OpenRouterError: If the underlying client is not
                initialized, or if the OpenRouter API request fails.
        """
        self._ensure_client_ready()
        messages = self._build_messages(prompt, system_prompt)

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
            raise OpenRouterError(
                f"OpenRouter API streaming request failed: {exc}", original_exception=exc
            ) from exc
        except Exception as exc:
            raise OpenRouterError(
                "An unexpected error occurred during OpenRouter streaming.",
                original_exception=exc,
            ) from exc

    # -------------------------------------------------------------------
    # Diagnostics hooks
    # -------------------------------------------------------------------

    def _do_count_tokens(self, text: str) -> int:
        """Estimate the number of tokens a request would use for the given text.

        OpenRouter can route a single request to many different
        underlying models, each with its own tokenizer, so no single
        exact token count is available without knowing which model
        will ultimately serve the request. This provides a reasonable
        approximation based on average English text density.

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
        """Verify that the OpenRouter client is initialized and reachable.

        Issues a minimal chat completion request with a very small
        token budget, which confirms both authentication and
        connectivity at negligible cost.

        Returns:
            ``True`` if the health check succeeds, ``False`` otherwise.
        """
        if self._client is None:
            raise OpenRouterError("OpenRouter provider is not initialized: API key missing or unconfigured.")

        self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": _ROLE_USER, "content": _HEALTH_CHECK_PROMPT}],
            max_tokens=1,
            stream=False,
        )
        return True

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _ensure_client_ready(self) -> None:
        """Verify the OpenRouter client is initialized before issuing a request.

        Raises:
            OpenRouterError: If :meth:`initialize` has not been called
                successfully, or the client is otherwise unavailable.
        """
        if not self.is_available or self._client is None:
            raise OpenRouterError(
                "OpenRouter provider is not initialized. Call initialize() "
                "before issuing requests."
            )

    def _build_messages(
        self, prompt: str, system_prompt: str | None
    ) -> list[dict[str, str]]:
        """Build the chat message list for an OpenRouter chat completions request.

        Args:
            prompt: The user-facing prompt.
            system_prompt: An optional system-level instruction.

        Returns:
            A list of chat messages in the OpenAI-compatible message
            format used by OpenRouter.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": _ROLE_SYSTEM, "content": system_prompt})
        messages.append({"role": _ROLE_USER, "content": prompt})
        return messages


__all__ = [
    "OpenRouterProvider",
]
