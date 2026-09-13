"""Google Gemini provider implementation for NOVA.

This module implements :class:`GeminiProvider`, the concrete
:class:`~providers.base_provider.BaseProvider` subclass that connects
NOVA to Google's Gemini models via the official ``google-genai`` SDK.

This module contains only Gemini-specific mechanics: constructing and
tearing down the ``google.genai.Client``, translating Gemini SDK
calls into the base class's abstract hooks, and translating Gemini
SDK exceptions into :class:`~core.exceptions.GeminiError`. Logging,
timing, common argument validation, and lifecycle state tracking are
all handled once, in :class:`~providers.base_provider.BaseProvider`,
and are intentionally not duplicated here.

The Gemini API key is never read from an environment variable
directly in this module; it is obtained exclusively through
``config.settings.settings``.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final

from config.settings import settings
from core.exceptions import GeminiError
from core.logger import get_logger
from google import genai
from google.genai import errors as genai_errors
from google.genai import types as genai_types
from providers.base_provider import BaseProvider

logger = get_logger(__name__)

# The default Gemini model used for text and multimodal requests. This
# is a non-secret identifier and is intentionally defined here, local
# to the Gemini provider, rather than in application configuration.
_DEFAULT_MODEL: Final[str] = "gemini-2.5-flash"

# A minimal, low-cost prompt used solely to verify connectivity during
# health checks; it is never surfaced to end users.
_HEALTH_CHECK_PROMPT: Final[str] = "ping"


class GeminiProvider(BaseProvider):
    """AI provider backed by Google Gemini, via the ``google-genai`` SDK.

    Attributes:
        _client: The underlying ``google.genai.Client`` instance, or
            ``None`` if the provider has not been initialized.
        _model: The Gemini model identifier used for all requests
            issued by this provider instance.
    """

    def __init__(self, model: str = _DEFAULT_MODEL) -> None:
        """Initialize a Gemini provider instance.

        Args:
            model: The Gemini model identifier to use for all
                requests. Defaults to :data:`_DEFAULT_MODEL`.
        """
        super().__init__()
        self._client: genai.Client | None = None
        self._model: str = model

    # -------------------------------------------------------------------
    # Identity
    # -------------------------------------------------------------------

    @property
    def provider_name(self) -> str:
        """Return the unique name of this provider.

        Returns:
            The literal string ``"gemini"``.
        """
        return "gemini"

    # -------------------------------------------------------------------
    # Capabilities
    # -------------------------------------------------------------------

    def supports_streaming(self) -> bool:
        """Report that Gemini supports streaming responses.

        Returns:
            ``True``.
        """
        return True

    def supports_vision(self) -> bool:
        """Report that Gemini supports image understanding.

        Returns:
            ``True``.
        """
        return True

    def supports_tools(self) -> bool:
        """Report that Gemini supports tool use.

        Returns:
            ``True``.
        """
        return True

    def supports_function_calling(self) -> bool:
        """Report that Gemini supports structured function calling.

        Returns:
            ``True``.
        """
        return True

    def supports_embeddings(self) -> bool:
        """Report that this provider does not currently implement embeddings.

        Returns:
            ``False``.
        """
        return False

    def supports_audio(self) -> bool:
        """Report that this provider does not currently implement audio input.

        Returns:
            ``False``.
        """
        return False

    def supports_images(self) -> bool:
        """Report that Gemini supports image generation.

        Returns:
            ``True``.
        """
        return True

    # -------------------------------------------------------------------
    # Lifecycle hooks
    # -------------------------------------------------------------------

    def _do_initialize(self) -> None:
        """Construct the underlying Gemini client.

        The client is constructed exactly once per provider instance;
        idempotency across repeated calls to
        :meth:`~providers.base_provider.BaseProvider.initialize` is
        already enforced by the base class.

        Raises:
            GeminiError: If the Gemini API key is missing or the
                client fails to construct.
        """
        api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
        if not api_key.strip() or api_key == "PASTE_MY_NEW_GEMINI_API_KEY_HERE":
            raise GeminiError("GEMINI_API_KEY is missing. Add it to the .env file.")

        try:
            self._client = genai.Client(api_key=api_key)
        except Exception as exc:
            raise GeminiError(
                "Failed to construct the Gemini client.", original_exception=exc
            ) from exc

    def _do_shutdown(self) -> None:
        """Release the underlying Gemini client."""
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
        """Generate a complete response using the Gemini API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Returns:
            The generated response text.

        Raises:
            GeminiError: If the underlying client is not initialized,
                or if the Gemini API request fails.
        """
        self._ensure_client_ready()
        config = self._build_generation_config(system_prompt, temperature, max_tokens)

        try:
            response = self._client.models.generate_content(  # type: ignore[union-attr]
                model=self._model,
                contents=prompt,
                config=config,
            )
        except genai_errors.APIError as exc:
            raise GeminiError(
                f"Gemini API request failed: {exc.message}", original_exception=exc
            ) from exc
        except Exception as exc:
            raise GeminiError(
                "An unexpected error occurred during Gemini generation.",
                original_exception=exc,
            ) from exc

        if not response.text:
            raise GeminiError("Gemini returned an empty response.")

        return response.text

    def _do_stream_response(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> Iterator[str]:
        """Generate a streaming response using the Gemini API.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Yields:
            Successive text chunks of the generated response.

        Raises:
            GeminiError: If the underlying client is not initialized,
                or if the Gemini API request fails.
        """
        self._ensure_client_ready()
        config = self._build_generation_config(system_prompt, temperature, max_tokens)

        try:
            stream = self._client.models.generate_content_stream(  # type: ignore[union-attr]
                model=self._model,
                contents=prompt,
                config=config,
            )
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except genai_errors.APIError as exc:
            raise GeminiError(
                f"Gemini API streaming request failed: {exc.message}",
                original_exception=exc,
            ) from exc
        except Exception as exc:
            raise GeminiError(
                "An unexpected error occurred during Gemini streaming.",
                original_exception=exc,
            ) from exc

    # -------------------------------------------------------------------
    # Diagnostics hooks
    # -------------------------------------------------------------------

    def _do_count_tokens(self, text: str) -> int:
        """Count the number of tokens Gemini would use for the given text.

        Args:
            text: The text to count tokens for.

        Returns:
            The total number of tokens ``text`` would consume.

        Raises:
            GeminiError: If the underlying client is not initialized,
                or if the token-counting request fails.
        """
        self._ensure_client_ready()

        try:
            result = self._client.models.count_tokens(  # type: ignore[union-attr]
                model=self._model,
                contents=text,
            )
        except genai_errors.APIError as exc:
            raise GeminiError(
                f"Gemini token counting failed: {exc.message}", original_exception=exc
            ) from exc
        except Exception as exc:
            raise GeminiError(
                "An unexpected error occurred while counting Gemini tokens.",
                original_exception=exc,
            ) from exc

        return int(result.total_tokens)

    def _do_health_check(self) -> bool:
        """Verify that the Gemini client is initialized and reachable.

        Issues a minimal token-counting request against the configured
        model, which confirms both authentication and connectivity
        without incurring the cost of a full generation request.

        Returns:
            ``True`` if the health check succeeds, ``False`` otherwise.
        """
        if self._client is None:
            raise GeminiError("Gemini provider is not initialized: API key missing or unconfigured.")

        self._client.models.count_tokens(
            model=self._model,
            contents=_HEALTH_CHECK_PROMPT,
        )
        return True

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _ensure_client_ready(self) -> None:
        """Verify the Gemini client is initialized before issuing a request.

        Raises:
            GeminiError: If :meth:`initialize` has not been called
                successfully, or the client is otherwise unavailable.
        """
        if not self.is_available or self._client is None:
            raise GeminiError(
                "Gemini provider is not initialized. Call initialize() before "
                "issuing requests."
            )

    def _build_generation_config(
        self,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> genai_types.GenerateContentConfig:
        """Build a Gemini generation configuration for a request.

        Args:
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Returns:
            A populated ``google.genai.types.GenerateContentConfig``
            instance.
        """
        return genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )


__all__ = [
    "GeminiProvider",
]
