"""Abstract base class for all AI providers used by NOVA.

This module defines :class:`BaseProvider`, the contract that every
concrete AI provider (Gemini, Groq, OpenRouter, Cerebras, and any
future provider) must implement. It exists so that
``core.lifecycle``, ``core.registry``, and any orchestration logic
built on top of them can work with AI providers polymorphically,
without knowing which specific provider is behind the interface.

Design:
    Public methods (:meth:`initialize`, :meth:`shutdown`,
    :meth:`generate_response`, :meth:`stream_response`,
    :meth:`health_check`, :meth:`count_tokens`) are concrete. They
    provide the cross-cutting behavior every provider needs for free:
    logging, response timing, common argument validation, and
    translation of unexpected exceptions into
    :class:`~core.exceptions.AIProviderError`. Each of these public
    methods delegates the actual provider-specific work to a
    corresponding protected abstract hook (for example,
    :meth:`generate_response` delegates to
    :meth:`_do_generate_response`), which concrete subclasses must
    implement.

    Capability query methods (:meth:`supports_vision`,
    :meth:`supports_streaming`, and so on) are concrete and default to
    ``False``. A concrete provider overrides only the capabilities it
    actually supports, so the base class never has to guess at or
    fake a provider's capabilities.

No provider-specific logic, API keys, or model names appear in this
module. Those belong exclusively in each concrete provider's own
module under ``providers/``.
"""

from __future__ import annotations

import threading
from typing import Final
import time
from abc import ABC, abstractmethod
from collections.abc import Iterator

from core.exceptions import AIProviderError
from core.logger import get_logger

logger = get_logger(__name__)

_MIN_TEMPERATURE: Final[float] = 0.0
_MAX_TEMPERATURE: Final[float] = 2.0


class BaseProvider(ABC):
    """Abstract base class for all AI providers integrated into NOVA.

    Concrete subclasses represent a single AI provider (for example,
    Google Gemini) and are responsible only for the provider-specific
    mechanics of connecting to that provider's API and translating
    requests and responses. Every cross-cutting concern — logging,
    timing, input validation, exception translation, and lifecycle
    state tracking — is handled once, here, in the base class.

    Attributes:
        _initialized: Whether :meth:`initialize` has completed
            successfully without a subsequent :meth:`shutdown`.
        _lock: A reentrant lock guarding lifecycle state transitions,
            so :meth:`initialize` and :meth:`shutdown` are safe to
            call from multiple threads.
    """

    def __init__(self) -> None:
        """Initialize shared provider state.

        Concrete subclasses that override ``__init__`` must call
        ``super().__init__()`` before performing any provider-specific
        setup, so that lifecycle state tracking is correctly
        established.
        """
        self._initialized: bool = False
        self._lock = threading.RLock()

    # -------------------------------------------------------------------
    # Identity and metadata
    # -------------------------------------------------------------------

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique, human-readable name of this provider.

        Returns:
            The provider's name (for example, ``"gemini"``).
        """
        ...

    @property
    def is_available(self) -> bool:
        """Report whether this provider is currently initialized and usable.

        Returns:
            ``True`` if :meth:`initialize` has completed successfully
            and :meth:`shutdown` has not since been called, ``False``
            otherwise.
        """
        with self._lock:
            return self._initialized

    def get_metadata(self) -> dict[str, object]:
        """Return descriptive metadata about this provider.

        Returns:
            A dictionary describing the provider's name, availability,
            and declared capabilities. Intended for diagnostics,
            health dashboards, and provider-selection logic.
        """
        return {
            "provider_name": self.provider_name,
            "is_available": self.is_available,
            "supports_vision": self.supports_vision(),
            "supports_streaming": self.supports_streaming(),
            "supports_tools": self.supports_tools(),
            "supports_function_calling": self.supports_function_calling(),
            "supports_embeddings": self.supports_embeddings(),
            "supports_audio": self.supports_audio(),
            "supports_images": self.supports_images(),
        }

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize this provider, making it ready to serve requests.

        Delegates the actual connection or client-construction work to
        :meth:`_do_initialize`. Calling this method more than once
        without an intervening :meth:`shutdown` is a no-op.

        Raises:
            AIProviderError: If initialization fails for any reason.
        """
        with self._lock:
            if self._initialized:
                logger.warning(
                    "[%s] initialize() called but provider is already initialized.",
                    self.provider_name,
                )
                return

            logger.info("[%s] Initializing provider.", self.provider_name)
            start_time = time.monotonic()
            try:
                self._do_initialize()
            except AIProviderError:
                raise
            except Exception as exc:
                raise self._translate_exception(exc, "initialization") from exc

            self._initialized = True
            elapsed = time.monotonic() - start_time
            logger.info(
                "[%s] Provider initialized successfully in %.3fs.",
                self.provider_name,
                elapsed,
            )

    def shutdown(self) -> None:
        """Shut down this provider, releasing any held resources.

        Delegates the actual teardown work to :meth:`_do_shutdown`.
        Calling this method when the provider is not currently
        initialized is a no-op.

        Raises:
            AIProviderError: If shutdown fails for any reason.
        """
        with self._lock:
            if not self._initialized:
                logger.warning(
                    "[%s] shutdown() called but provider is not initialized.",
                    self.provider_name,
                )
                return

            logger.info("[%s] Shutting down provider.", self.provider_name)
            start_time = time.monotonic()
            try:
                self._do_shutdown()
            except AIProviderError:
                raise
            except Exception as exc:
                raise self._translate_exception(exc, "shutdown") from exc

            self._initialized = False
            elapsed = time.monotonic() - start_time
            logger.info(
                "[%s] Provider shut down successfully in %.3fs.",
                self.provider_name,
                elapsed,
            )

    # -------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------

    def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> str:
        """Generate a single, complete response to a prompt.

        Validates common arguments, times the request, and delegates
        the actual generation work to :meth:`_do_generate_response`.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction that
                shapes the provider's behavior for this request.
            temperature: Sampling temperature controlling response
                randomness. Must be between 0.0 and 2.0 inclusive.
            max_tokens: An optional upper bound on the number of
                tokens to generate. Must be a positive integer if
                provided.

        Returns:
            The generated response text.

        Raises:
            AIProviderError: If argument validation fails, or if the
                underlying provider fails to generate a response.
        """
        self._validate_generation_arguments(prompt, temperature, max_tokens)

        logger.debug(
            "[%s] generate_response called (temperature=%s, max_tokens=%s).",
            self.provider_name,
            temperature,
            max_tokens,
        )
        start_time = time.monotonic()
        try:
            response = self._do_generate_response(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AIProviderError:
            raise
        except Exception as exc:
            raise self._translate_exception(exc, "response generation") from exc
        finally:
            elapsed = time.monotonic() - start_time
            logger.info(
                "[%s] generate_response completed in %.3fs.", self.provider_name, elapsed
            )
        from core.response_cleaner import clean_model_response
        return clean_model_response(response)


    def stream_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Iterator[str]:
        """Generate a response to a prompt as an incremental stream of text.

        Validates common arguments, times the full streaming duration,
        and delegates the actual streaming work to
        :meth:`_do_stream_response`.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction that
                shapes the provider's behavior for this request.
            temperature: Sampling temperature controlling response
                randomness. Must be between 0.0 and 2.0 inclusive.
            max_tokens: An optional upper bound on the number of
                tokens to generate. Must be a positive integer if
                provided.

        Yields:
            Successive text chunks of the generated response.

        Raises:
            AIProviderError: If argument validation fails, or if the
                underlying provider fails while streaming a response.
        """
        self._validate_generation_arguments(prompt, temperature, max_tokens)

        logger.debug(
            "[%s] stream_response called (temperature=%s, max_tokens=%s).",
            self.provider_name,
            temperature,
            max_tokens,
        )
        start_time = time.monotonic()
        try:
            yield from self._do_stream_response(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AIProviderError:
            raise
        except Exception as exc:
            raise self._translate_exception(exc, "response streaming") from exc
        finally:
            elapsed = time.monotonic() - start_time
            logger.info(
                "[%s] stream_response completed in %.3fs.", self.provider_name, elapsed
            )

    # -------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------

    def health_check(self) -> bool:
        """Check whether this provider is currently reachable and healthy.

        Delegates to :meth:`_do_health_check`. Unlike other public
        methods, a failure here is reported as ``False`` rather than
        raised, since health checks are expected to be used
        defensively (for example, to decide whether to route a
        request to this provider at all).

        Returns:
            ``True`` if the provider responded successfully to a
            health check, ``False`` otherwise.
        """
        start_time = time.monotonic()
        try:
            is_healthy = self._do_health_check()
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if is_healthy:
                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.record_provider_success(self.provider_name, latency_ms=elapsed_ms)
                except Exception:
                    pass
                return True
            else:
                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.record_provider_failure(
                        self.provider_name,
                        status="UNAVAILABLE",
                        error_msg="Provider probe returned unsuccessful",
                        latency_ms=elapsed_ms,
                    )
                except Exception:
                    pass
                return False
        except Exception as exc:
            elapsed_ms = (time.monotonic() - start_time) * 1000
            logger.warning(
                "[%s] health_check failed: %s", self.provider_name, exc
            )
            try:
                from ui.health_checker import DashboardStatsManager
                from providers.provider_manager import classify_provider_error
                err_status, err_msg, retry_after = classify_provider_error(exc)
                DashboardStatsManager.record_provider_failure(
                    self.provider_name,
                    status=err_status,
                    error_msg=err_msg,
                    latency_ms=elapsed_ms,
                    retry_after=retry_after,
                )
            except Exception:
                pass
            return False
        finally:
            elapsed = time.monotonic() - start_time
            logger.debug("[%s] health_check completed in %.3fs.", self.provider_name, elapsed)

    def count_tokens(self, text: str) -> int:
        """Count the number of tokens the provider would use for a given text.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens ``text`` would consume for this
            provider.

        Raises:
            AIProviderError: If ``text`` is not a string, or if token
                counting fails for any other reason.
        """
        if not isinstance(text, str):
            raise AIProviderError(
                f"[{self.provider_name}] count_tokens requires a string, got "
                f"{type(text).__name__}."
            )

        try:
            return self._do_count_tokens(text)
        except AIProviderError:
            raise
        except Exception as exc:
            raise self._translate_exception(exc, "token counting") from exc

    # -------------------------------------------------------------------
    # Capability declarations
    # -------------------------------------------------------------------

    def supports_vision(self) -> bool:
        """Report whether this provider can process image input.

        Returns:
            ``False`` by default. Providers with vision capability
            must override this method to return ``True``.
        """
        return False

    def supports_streaming(self) -> bool:
        """Report whether this provider supports streaming responses.

        Returns:
            ``False`` by default. Providers with streaming capability
            must override this method to return ``True``.
        """
        return False

    def supports_tools(self) -> bool:
        """Report whether this provider supports tool use.

        Returns:
            ``False`` by default. Providers with tool-use capability
            must override this method to return ``True``.
        """
        return False

    def supports_function_calling(self) -> bool:
        """Report whether this provider supports structured function calling.

        Returns:
            ``False`` by default. Providers with function-calling
            capability must override this method to return ``True``.
        """
        return False

    def supports_embeddings(self) -> bool:
        """Report whether this provider can generate text embeddings.

        Returns:
            ``False`` by default. Providers with embedding capability
            must override this method to return ``True``.
        """
        return False

    def supports_audio(self) -> bool:
        """Report whether this provider can process audio input.

        Returns:
            ``False`` by default. Providers with audio capability
            must override this method to return ``True``.
        """
        return False

    def supports_images(self) -> bool:
        """Report whether this provider can generate image output.

        Returns:
            ``False`` by default. Providers with image-generation
            capability must override this method to return ``True``.
        """
        return False

    # -------------------------------------------------------------------
    # Protected abstract hooks (implemented by concrete providers)
    # -------------------------------------------------------------------

    @abstractmethod
    def _do_initialize(self) -> None:
        """Perform provider-specific initialization.

        Concrete subclasses implement this to construct API clients,
        validate connectivity, or perform any other setup required
        before the provider can serve requests.

        Raises:
            Exception: Any exception raised here is caught by
                :meth:`initialize` and translated into an
                :class:`~core.exceptions.AIProviderError`.
        """
        ...

    @abstractmethod
    def _do_shutdown(self) -> None:
        """Perform provider-specific teardown.

        Concrete subclasses implement this to close connections,
        release resources, or perform any other cleanup required when
        the provider is no longer needed.

        Raises:
            Exception: Any exception raised here is caught by
                :meth:`shutdown` and translated into an
                :class:`~core.exceptions.AIProviderError`.
        """
        ...

    @abstractmethod
    def _do_generate_response(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> str:
        """Perform the provider-specific work of generating a response.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Returns:
            The generated response text.

        Raises:
            Exception: Any exception raised here is caught by
                :meth:`generate_response` and translated into an
                :class:`~core.exceptions.AIProviderError`.
        """
        ...

    @abstractmethod
    def _do_stream_response(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> Iterator[str]:
        """Perform the provider-specific work of streaming a response.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.

        Yields:
            Successive text chunks of the generated response.

        Raises:
            Exception: Any exception raised here is caught by
                :meth:`stream_response` and translated into an
                :class:`~core.exceptions.AIProviderError`.
        """
        ...

    @abstractmethod
    def _do_count_tokens(self, text: str) -> int:
        """Perform the provider-specific work of counting tokens.

        Args:
            text: The text to count tokens for.

        Returns:
            The number of tokens ``text`` would consume for this
            provider.

        Raises:
            Exception: Any exception raised here is caught by
                :meth:`count_tokens` and translated into an
                :class:`~core.exceptions.AIProviderError`.
        """
        ...

    @abstractmethod
    def _do_health_check(self) -> bool:
        """Perform the provider-specific work of checking provider health.

        Returns:
            ``True`` if the provider is reachable and healthy,
            ``False`` otherwise.

        Raises:
            Exception: Any exception raised here is caught by
                :meth:`health_check`, logged, and treated as an
                unhealthy result.
        """
        ...

    # -------------------------------------------------------------------
    # Shared validation and exception translation
    # -------------------------------------------------------------------

    def _validate_generation_arguments(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int | None,
    ) -> None:
        """Validate arguments common to generation and streaming requests.

        Args:
            prompt: The prompt to validate.
            temperature: The sampling temperature to validate.
            max_tokens: The optional token limit to validate.

        Raises:
            AIProviderError: If ``prompt`` is not a non-empty string,
                if ``temperature`` is outside the supported range, or
                if ``max_tokens`` is not a positive integer when
                provided.
        """
        if not isinstance(prompt, str) or not prompt.strip():
            raise AIProviderError(
                f"[{self.provider_name}] prompt must be a non-empty string."
            )

        if not isinstance(temperature, (int, float)) or not (
            _MIN_TEMPERATURE <= temperature <= _MAX_TEMPERATURE
        ):
            raise AIProviderError(
                f"[{self.provider_name}] temperature must be a number between "
                f"{_MIN_TEMPERATURE} and {_MAX_TEMPERATURE}, got {temperature!r}."
            )

        if max_tokens is not None and (not isinstance(max_tokens, int) or max_tokens <= 0):
            raise AIProviderError(
                f"[{self.provider_name}] max_tokens must be a positive integer "
                f"when provided, got {max_tokens!r}."
            )

    def _translate_exception(self, exc: Exception, operation: str) -> AIProviderError:
        """Translate an arbitrary exception into a provider-specific error.

        This ensures that no matter what exception type a concrete
        provider's underlying SDK raises, callers of this base class
        only ever have to handle :class:`~core.exceptions.AIProviderError`
        (or one of its subclasses, if the concrete provider raises
        one directly).

        Args:
            exc: The original exception that was raised.
            operation: A short description of the operation that
                failed (for example, ``"response generation"``), used
                to produce a clearer error message.

        Returns:
            An :class:`~core.exceptions.AIProviderError` wrapping
            ``exc``, with the original exception preserved.
        """
        return AIProviderError(
            f"[{self.provider_name}] {operation} failed: {exc}",
            original_exception=exc,
        )


__all__ = [
    "BaseProvider",
]
