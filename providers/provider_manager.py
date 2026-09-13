"""Central AI provider management and routing layer for NOVA.

This module implements :class:`ProviderManager`, the component that
acts as NOVA's central AI brain. It automatically registers every
concrete AI provider NOVA ships with (Gemini, Groq, OpenRouter, and
Cerebras), manages their lifecycle, monitors their health, routes
requests to the most appropriate provider for a given task, falls
back to alternative providers on failure, and tracks runtime usage
statistics.

Architecture:
    ``ProviderManager`` composes two responsibilities that are kept
    deliberately separate:

    - **Provider lifecycle and storage** (registration, removal,
      initialization, shutdown, health checks) is owned directly by
      :class:`ProviderManager`.
    - **Routing decisions** (which provider to prefer for a given
      kind of task) are owned by the internal :class:`_RoutingEngine`,
      which knows nothing about provider lifecycle, network calls, or
      statistics. This separation means routing priorities can be
      changed or extended without touching any lifecycle or
      networking code, and vice versa.

Every provider is accessed exclusively through the
:class:`~providers.base_provider.BaseProvider` interface. Adding a
new provider in the future requires only adding it to the tuple of
default provider classes and, optionally, to the routing priority
tables; no other logic in this module needs to change.

No internal SDK exception ever escapes this module directly. All
failures are surfaced to callers as
:class:`~core.exceptions.AIProviderError` or one of the manager-level
exceptions defined here.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

from core.exceptions import AIProviderError
from core.logger import get_logger
from providers.base_provider import BaseProvider
from providers.cerebras import CerebrasProvider
from providers.gemini import GeminiProvider
from providers.groq import GroqProvider
from providers.openrouter import OpenRouterProvider

logger = get_logger(__name__)

SelectionMode = Literal["auto", "manual"]


class TaskType(str, Enum):
    """The kinds of tasks NOVA's automatic routing engine can optimize for.

    Attributes:
        CODING: Tasks primarily involving writing or reasoning about
            source code.
        REASONING: Tasks requiring deep, multi-step reasoning.
        FAST: Tasks where response latency is the primary concern.
        CHEAP: Tasks where minimizing request cost is the primary
            concern.
        GENERAL: General-purpose conversational tasks with no
            specific optimization priority.
    """

    CODING = "coding"
    REASONING = "reasoning"
    FAST = "fast"
    CHEAP = "cheap"
    GENERAL = "general"


# Ordered provider-name priority tables, one per task type, used by
# the automatic routing engine. Order matters: the first available
# provider in the tuple is preferred.
_ROUTING_PRIORITIES: dict[TaskType, tuple[str, ...]] = {
    TaskType.CODING: ("gemini", "groq", "openrouter", "cerebras"),
    TaskType.REASONING: ("gemini", "openrouter", "groq", "cerebras"),
    TaskType.FAST: ("groq", "cerebras", "gemini", "openrouter"),
    TaskType.CHEAP: ("cerebras", "groq", "gemini", "openrouter"),
    TaskType.GENERAL: ("gemini", "groq", "openrouter", "cerebras"),
}


class ProviderNotFoundError(AIProviderError):
    """Raised when a requested provider is not registered in the manager."""

    default_message: str = "The requested provider is not registered."


class DuplicateProviderError(AIProviderError):
    """Raised when attempting to register a provider name that already exists."""

    default_message: str = "A provider with this name is already registered."


class AllProvidersFailedError(AIProviderError):
    """Raised when every candidate provider fails to fulfill a request.

    This is the only failure type callers of
    :meth:`ProviderManager.generate_response` and
    :meth:`ProviderManager.stream_response` need to handle for a
    request that could not be fulfilled by any provider; the specific
    underlying provider errors are logged internally rather than
    exposed directly to the caller.
    """

    default_message: str = "All candidate providers failed to fulfill the request."


@dataclass
class ProviderRuntimeStatus:
    """Real-time diagnostic health and latency status for an AI provider."""

    name: str
    status: str = "UNKNOWN"  # HEALTHY | DEGRADED | WARNING | RATE LIMITED | QUOTA EXCEEDED | OFFLINE | ERROR | UNKNOWN
    last_latency_ms: float | None = None
    last_request_time: float | None = None
    last_success_time: float | None = None
    last_error: str | None = None
    retry_after_seconds: float | None = None
    consecutive_failures: int = 0
    total_requests: int = 0
    successful_requests: int = 0


@dataclass
class ProviderStatistics:
    """Runtime usage statistics tracked by :class:`ProviderManager`.

    Attributes:
        total_requests: The total number of requests attempted,
            regardless of outcome.
        successful_requests: The number of requests that were
            ultimately fulfilled by some provider.
        failed_requests: The number of requests for which every
            candidate provider failed.
        provider_usage_count: A mapping of provider name to the number
            of successful requests it has fulfilled.
        last_provider_used: The name of the provider that most
            recently fulfilled a request successfully, or ``None`` if
            no request has succeeded yet.
        total_response_time_seconds: The cumulative wall-clock time,
            in seconds, spent on all successful requests.
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    provider_usage_count: dict[str, int] = field(default_factory=dict)
    last_provider_used: str | None = None
    total_response_time_seconds: float = 0.0

    @property
    def average_response_time_seconds(self) -> float:
        """Return the average response time across all successful requests.

        Returns:
            The average response time in seconds, or ``0.0`` if no
            request has succeeded yet.
        """
        if self.successful_requests == 0:
            return 0.0
        return self.total_response_time_seconds / self.successful_requests


class _RoutingEngine:
    """Isolated routing logic for automatic provider selection.

    ``_RoutingEngine`` knows the priority order of providers for each
    :class:`TaskType`, but nothing about provider lifecycle, network
    calls, or statistics. It is used exclusively by
    :class:`ProviderManager` to decide which provider to try next.
    """

    def priority_order(self, task_type: TaskType) -> tuple[str, ...]:
        """Return the full provider priority order for a task type.

        Args:
            task_type: The kind of task being routed.

        Returns:
            An ordered tuple of provider names, most preferred first,
            regardless of whether each provider is currently
            available.
        """
        return _ROUTING_PRIORITIES[task_type]

    def select(
        self, task_type: TaskType, available_provider_names: tuple[str, ...]
    ) -> str | None:
        """Select the most preferred available provider for a task type.

        Args:
            task_type: The kind of task being routed.
            available_provider_names: The names of providers that are
                currently available for selection.

        Returns:
            The name of the most preferred available provider, or
            ``None`` if none of the providers in the priority order
            are currently available.
        """
        for candidate_name in self.priority_order(task_type):
            if candidate_name in available_provider_names:
                return candidate_name
        return None


def classify_provider_error(exc: Exception) -> tuple[str, str, float | None]:
    """Classify exception into standard status, clean diagnostic message, and optional retry delay.

    Statuses: HEALTHY, DEGRADED, RATE_LIMITED, QUOTA_EXCEEDED, UNAVAILABLE, AUTH_ERROR, NETWORK_ERROR, TIMEOUT, CONFIG_ERROR, UNKNOWN.
    """
    err_str = str(exc)
    err_lower = err_str.lower()
    retry_after: float | None = None

    import re
    m = re.search(r"retry\s*(?:in|after)?\s*[:\s]*(\d+)\s*(?:s|sec|seconds)?", err_lower)
    if m:
        try:
            retry_after = float(m.group(1))
        except ValueError:
            pass

    if any(k in err_lower for k in ["401", "403", "unauthorized", "forbidden", "permission_denied", "invalid api key", "invalid_api_key"]):
        return "AUTH_ERROR", "Authentication / Permission error (HTTP 401/403)", retry_after
    elif "quota" in err_lower or "insufficient_quota" in err_lower or "exceeded your current quota" in err_lower or "402" in err_lower:
        return "QUOTA_EXCEEDED", "API Quota Exceeded (HTTP 402/429 Quota)", retry_after
    elif "429" in err_lower or "rate limit" in err_lower or "too many requests" in err_lower or "ratelimit" in err_lower:
        return "RATE_LIMITED", "Rate limit reached (HTTP 429)", retry_after
    elif "404" in err_lower or "model_not_found" in err_lower or "not exist" in err_lower or "archived" in err_lower:
        clean = err_str.split("\n")[0].strip()
        return "CONFIG_ERROR", f"Model not found or archived: {clean[:50]}", retry_after
    elif "missing" in err_lower or "unconfigured" in err_lower or "empty" in err_lower or "not initialized" in err_lower:
        return "CONFIG_ERROR", "API key missing/unconfigured", retry_after
    elif "timed out" in err_lower or "timeout" in err_lower:
        return "TIMEOUT", "Request timed out", retry_after
    elif "connection" in err_lower or "network" in err_lower or "offline" in err_lower or "dns" in err_lower or "connect" in err_lower:
        return "NETWORK_ERROR", "Network connectivity error", retry_after
    elif "degraded" in err_lower or "slow" in err_lower:
        return "DEGRADED", "Provider performance degraded", retry_after
    else:
        clean = err_str.split("\n")[0].strip()
        if len(clean) > 80:
            clean = clean[:77] + "..."
        return "UNAVAILABLE", clean or "API request failed", retry_after


class ProviderManager:
    """NOVA's central AI provider registry, router, and orchestrator.

    On construction, ``ProviderManager`` automatically instantiates
    and registers every default AI provider NOVA ships with. It then
    exposes a unified interface for initializing, monitoring, and
    issuing requests to those providers, transparently routing each
    request to the most suitable provider and falling back to
    alternatives if a provider fails.

    Attributes:
        _providers: The internal mapping of provider name to the
            registered :class:`~providers.base_provider.BaseProvider`
            instance.
        _router: The routing engine used for automatic provider
            selection.
        _statistics: Runtime usage statistics for this manager.
        _lock: A reentrant lock guarding all internal state, making
            every public operation thread-safe.
    """

    #: Concrete provider classes registered automatically on construction.
    _DEFAULT_PROVIDER_CLASSES: tuple[type[BaseProvider], ...] = (
        GeminiProvider,
        GroqProvider,
        OpenRouterProvider,
        CerebrasProvider,
    )

    def __init__(self) -> None:
        """Construct a provider manager and register all default providers.

        A failure to construct or register any single default
        provider is logged and does not prevent the remaining default
        providers from being registered.
        """
        self._providers: dict[str, BaseProvider] = {}
        self._router: _RoutingEngine = _RoutingEngine()
        self._statistics: ProviderStatistics = ProviderStatistics()
        self._runtime_status: dict[str, ProviderRuntimeStatus] = {}
        self._lock: threading.RLock = threading.RLock()

        self._register_default_providers()

    def _register_default_providers(self) -> None:
        """Construct and register every default provider.

        Each provider class is instantiated and registered
        independently; a failure in one does not prevent the others
        from being registered.
        """
        for provider_class in self._DEFAULT_PROVIDER_CLASSES:
            try:
                provider_instance = provider_class()
                self.register_provider(provider_instance)
            except Exception as exc:
                logger.error(
                    "Failed to construct or register default provider '%s': %s",
                    provider_class.__name__,
                    exc,
                    exc_info=True,
                )

    # -------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------

    def register_provider(self, provider: BaseProvider) -> None:
        """Register a new provider instance.

        Args:
            provider: The provider instance to register. Its
                ``provider_name`` property is used as the registration
                key.

        Raises:
            DuplicateProviderError: If a provider is already
                registered under the same name.
        """
        with self._lock:
            name = provider.provider_name
            if name in self._providers:
                raise DuplicateProviderError(f"Provider '{name}' is already registered.")
            self._providers[name] = provider
            logger.info("Provider '%s' registered with the provider manager.", name)

    def remove_provider(self, provider_name: str) -> None:
        """Remove a previously registered provider by name.

        Args:
            provider_name: The unique name of the provider to remove.

        Raises:
            ProviderNotFoundError: If no provider is registered under
                ``provider_name``.
        """
        with self._lock:
            if provider_name not in self._providers:
                raise ProviderNotFoundError(
                    f"Cannot remove '{provider_name}': no provider is registered "
                    "under this name."
                )
            del self._providers[provider_name]
            logger.info("Provider '%s' removed from the provider manager.", provider_name)

    def provider_exists(self, provider_name: str) -> bool:
        """Check whether a provider is currently registered under a name.

        Args:
            provider_name: The unique name to check.

        Returns:
            ``True`` if a provider is registered under
            ``provider_name``, ``False`` otherwise.
        """
        with self._lock:
            return provider_name in self._providers

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize every registered provider.

        A failure to initialize one provider is logged and does not
        prevent the remaining providers from being initialized.
        """
        with self._lock:
            for name, provider in self._providers.items():
                try:
                    provider.initialize()
                    logger.info("Provider '%s' initialized successfully.", name)
                except Exception as exc:
                    logger.error(
                        "Provider '%s' failed to initialize: %s", name, exc, exc_info=True
                    )

    def shutdown(self) -> None:
        """Shut down every registered provider.

        A failure to shut down one provider is logged and does not
        prevent the remaining providers from being shut down.
        """
        with self._lock:
            for name, provider in self._providers.items():
                try:
                    provider.shutdown()
                    logger.info("Provider '%s' shut down successfully.", name)
                except Exception as exc:
                    logger.error(
                        "Provider '%s' failed to shut down cleanly: %s",
                        name,
                        exc,
                        exc_info=True,
                    )

    # -------------------------------------------------------------------
    # Retrieval and health
    # -------------------------------------------------------------------

    def get_provider(self, provider_name: str) -> BaseProvider:
        """Retrieve a registered provider instance by name.

        Args:
            provider_name: The unique name of the provider to
                retrieve.

        Returns:
            The registered provider instance.

        Raises:
            ProviderNotFoundError: If no provider is registered under
                ``provider_name``.
        """
        with self._lock:
            provider = self._providers.get(provider_name)
            if provider is None:
                raise ProviderNotFoundError(
                    f"No provider is registered under the name '{provider_name}'."
                )
            return provider

    def get_available_providers(self) -> tuple[str, ...]:
        """List the names of every provider that is currently initialized.

        Returns:
            A tuple of provider names for which ``is_available`` is
            ``True``.
        """
        with self._lock:
            return tuple(
                name for name, provider in self._providers.items() if provider.is_available
            )

    def health_check(self, provider_name: str | None = None) -> dict[str, bool]:
        """Perform a live health check against one or all registered providers.

        A provider whose health check raises an exception is treated
        as unhealthy rather than propagating the exception, so a
        single failing provider never prevents the remaining
        providers from being checked.

        Args:
            provider_name: If provided, only this provider is
                checked. If ``None``, every registered provider is
                checked.

        Returns:
            A mapping of provider name to a boolean indicating
            whether that provider is currently healthy.

        Raises:
            ProviderNotFoundError: If ``provider_name`` is provided but
                no provider is registered under that name.
        """
        with self._lock:
            if provider_name is not None:
                providers_to_check = {provider_name: self.get_provider(provider_name)}
            else:
                providers_to_check = dict(self._providers)

        results: dict[str, bool] = {}
        for name, provider in providers_to_check.items():
            try:
                is_healthy = provider.health_check()
            except Exception as exc:
                logger.error(
                    "Health check for provider '%s' raised an exception: %s",
                    name,
                    exc,
                    exc_info=True,
                )
                is_healthy = False
            results[name] = is_healthy
            logger.debug("Health check result for '%s': %s", name, is_healthy)
        return results

    def provider_capabilities(
        self, provider_name: str | None = None
    ) -> dict[str, object] | dict[str, dict[str, object]]:
        """Return capability and metadata information for one or all providers.

        Args:
            provider_name: If provided, only this provider's metadata
                is returned. If ``None``, metadata for every
                registered provider is returned, keyed by provider
                name.

        Returns:
            If ``provider_name`` is provided, a single metadata
            dictionary for that provider. Otherwise, a mapping of
            provider name to that provider's metadata dictionary.

        Raises:
            ProviderNotFoundError: If ``provider_name`` is provided but
                no provider is registered under that name.
        """
        with self._lock:
            if provider_name is not None:
                return self.get_provider(provider_name).get_metadata()
            return {name: provider.get_metadata() for name, provider in self._providers.items()}

    # -------------------------------------------------------------------
    # Routing
    # -------------------------------------------------------------------

    def choose_provider(
        self,
        task_type: TaskType | str = TaskType.GENERAL,
        mode: SelectionMode = "auto",
        provider_name: str | None = None,
    ) -> BaseProvider:
        """Choose a provider for a request, without issuing the request.

        Args:
            task_type: The kind of task to optimize provider selection
                for, used only when ``mode="auto"``.
            mode: ``"auto"`` to let the routing engine choose based on
                ``task_type``, or ``"manual"`` to explicitly select
                ``provider_name``.
            provider_name: The provider to select when ``mode="manual"``.
                Ignored when ``mode="auto"``.

        Returns:
            The chosen provider instance.

        Raises:
            AIProviderError: If ``mode`` is ``"manual"`` and
                ``provider_name`` is not provided, or if ``mode`` is
                not a recognized value.
            ProviderNotFoundError: If ``mode`` is ``"manual"`` and
                ``provider_name`` does not refer to a registered
                provider.
            AllProvidersFailedError: If ``mode`` is ``"auto"`` and no
                available provider exists for ``task_type``.
        """
        normalized_task_type = self._normalize_task_type(task_type)

        if mode == "manual":
            if provider_name is None:
                raise AIProviderError("Manual provider selection requires a provider_name.")
            provider = self.get_provider(provider_name)
            logger.info(
                "Manual routing selected provider '%s' for task_type='%s'.",
                provider_name,
                normalized_task_type.value,
            )
            return provider

        if mode == "auto":
            available_names = self.get_available_providers()
            chosen_name = self._router.select(normalized_task_type, available_names)
            if chosen_name is None:
                raise AllProvidersFailedError(
                    "No available provider could be selected for task_type "
                    f"'{normalized_task_type.value}'."
                )
            logger.info(
                "Automatic routing selected provider '%s' for task_type='%s'.",
                chosen_name,
                normalized_task_type.value,
            )
            return self.get_provider(chosen_name)

        raise AIProviderError(f"Unknown provider selection mode '{mode}'.")

    # -------------------------------------------------------------------
    # Generation
    # -------------------------------------------------------------------

    def generate_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        task_type: TaskType | str = TaskType.GENERAL,
        mode: SelectionMode = "auto",
        provider_name: str | None = None,
    ) -> str:
        """Generate a complete response, routing across providers as needed.

        Candidate providers are tried in priority order (or the single
        manually selected provider, if ``mode="manual"``). If a
        candidate fails or is unavailable, the next candidate is tried
        automatically.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.
            task_type: The kind of task to optimize routing for, used
                only when ``mode="auto"``.
            mode: ``"auto"`` to route automatically based on
                ``task_type``, or ``"manual"`` to use ``provider_name``
                exclusively.
            provider_name: The provider to use when ``mode="manual"``.

        Returns:
            The generated response text.

        Raises:
            AllProvidersFailedError: If every candidate provider fails
                or is unavailable.
            ProviderNotFoundError: If ``mode="manual"`` and
                ``provider_name`` does not refer to a registered
                provider.
        """
        normalized_task_type = self._normalize_task_type(task_type)
        candidates = self._resolve_candidates(normalized_task_type, mode, provider_name)

        self._record_request_start()
        last_error: Exception | None = None

        for idx, candidate_name in enumerate(candidates):
            provider = self._providers.get(candidate_name)
            if provider is None or not provider.is_available:
                continue

            rt = self._get_or_create_runtime_status(candidate_name)
            rt.last_request_time = time.time()
            rt.total_requests += 1

            start_time = time.monotonic()
            try:
                response_text = provider.generate_response(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:
                elapsed = time.monotonic() - start_time
                status_cat, clean_msg, retry_sec = self._classify_error(exc)

                rt.status = status_cat
                rt.last_latency_ms = round(elapsed * 1000, 1)
                rt.last_error = clean_msg
                rt.retry_after_seconds = retry_sec
                rt.consecutive_failures += 1

                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.record_provider_failure(
                        candidate_name,
                        status_cat,
                        clean_msg,
                        latency_ms=rt.last_latency_ms,
                        retry_after=retry_sec,
                    )
                except Exception:
                    pass

                logger.warning(
                    "Provider '%s' failed to generate a response in %.3fs: %s. "
                    "Attempting fallback.",
                    candidate_name,
                    elapsed,
                    exc,
                )
                last_error = exc
                continue

            elapsed = time.monotonic() - start_time
            lat_ms = round(elapsed * 1000, 1)
            rt.status = "HEALTHY"
            rt.last_latency_ms = lat_ms
            rt.last_success_time = time.time()
            rt.last_error = None
            rt.retry_after_seconds = None
            rt.consecutive_failures = 0
            rt.successful_requests += 1

            try:
                from ui.health_checker import DashboardStatsManager
                DashboardStatsManager.record_provider_success(
                    candidate_name,
                    latency_ms=lat_ms,
                    fallback_used=(idx > 0),
                    primary_failed=candidates[0] if idx > 0 else "",
                )
            except Exception:
                pass

            self._record_success(candidate_name, elapsed)
            logger.info(
                "Provider '%s' generated a response successfully in %.3fs.",
                candidate_name,
                elapsed,
            )
            return response_text

        self._record_failure()
        raise AllProvidersFailedError(
            "All candidate providers failed to generate a response.",
            original_exception=last_error,
        )

    def stream_response(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        task_type: TaskType | str = TaskType.GENERAL,
        mode: SelectionMode = "auto",
        provider_name: str | None = None,
    ) -> Iterator[str]:
        """Generate a streaming response, routing across providers as needed.

        Fallback to the next candidate provider is only possible
        before the first chunk of a stream has been yielded. Once a
        provider has begun streaming, a subsequent mid-stream failure
        is raised directly, since previously yielded chunks cannot be
        retracted from the caller.

        Args:
            prompt: The user-facing prompt to generate a response for.
            system_prompt: An optional system-level instruction.
            temperature: Sampling temperature controlling response
                randomness.
            max_tokens: An optional upper bound on generated tokens.
            task_type: The kind of task to optimize routing for, used
                only when ``mode="auto"``.
            mode: ``"auto"`` to route automatically based on
                ``task_type``, or ``"manual"`` to use ``provider_name``
                exclusively.
            provider_name: The provider to use when ``mode="manual"``.

        Yields:
            Successive text chunks of the generated response.

        Raises:
            AllProvidersFailedError: If every candidate provider fails
                before streaming begins, or if the streaming provider
                fails after streaming has already begun.
            ProviderNotFoundError: If ``mode="manual"`` and
                ``provider_name`` does not refer to a registered
                provider.
        """
        normalized_task_type = self._normalize_task_type(task_type)
        candidates = self._resolve_candidates(normalized_task_type, mode, provider_name)

        self._record_request_start()
        last_error: Exception | None = None

        for idx, candidate_name in enumerate(candidates):
            provider = self._providers.get(candidate_name)
            if provider is None or not provider.is_available:
                continue

            rt = self._get_or_create_runtime_status(candidate_name)
            rt.last_request_time = time.time()
            rt.total_requests += 1

            start_time = time.monotonic()
            try:
                chunk_iterator = provider.stream_response(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                first_chunk = next(chunk_iterator)
            except StopIteration:
                elapsed = time.monotonic() - start_time
                lat_ms = round(elapsed * 1000, 1)
                rt.status = "HEALTHY"
                rt.last_latency_ms = lat_ms
                rt.last_success_time = time.time()
                rt.last_error = None
                rt.retry_after_seconds = None
                rt.consecutive_failures = 0
                rt.successful_requests += 1

                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.record_provider_success(
                        candidate_name,
                        latency_ms=lat_ms,
                        fallback_used=(idx > 0),
                        primary_failed=candidates[0] if idx > 0 else "",
                    )
                except Exception:
                    pass

                self._record_success(candidate_name, elapsed)
                logger.info(
                    "Provider '%s' produced an empty stream in %.3fs.",
                    candidate_name,
                    elapsed,
                )
                return
            except Exception as exc:
                elapsed = time.monotonic() - start_time
                status_cat, clean_msg, retry_sec = self._classify_error(exc)
                rt.status = status_cat
                rt.last_latency_ms = round(elapsed * 1000, 1)
                rt.last_error = clean_msg
                rt.retry_after_seconds = retry_sec
                rt.consecutive_failures += 1

                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.record_provider_failure(
                        candidate_name,
                        status_cat,
                        clean_msg,
                        latency_ms=rt.last_latency_ms,
                        retry_after=retry_sec,
                    )
                except Exception:
                    pass

                logger.warning(
                    "Provider '%s' failed before streaming began (%.3fs): %s. "
                    "Attempting fallback.",
                    candidate_name,
                    elapsed,
                    exc,
                )
                last_error = exc
                continue

            logger.info("Provider '%s' began streaming a response.", candidate_name)
            yield first_chunk

            try:
                for chunk in chunk_iterator:
                    yield chunk
            except Exception as exc:
                elapsed = time.monotonic() - start_time
                status_cat, clean_msg, retry_sec = self._classify_error(exc)
                rt.status = status_cat
                rt.last_latency_ms = round(elapsed * 1000, 1)
                rt.last_error = clean_msg
                rt.retry_after_seconds = retry_sec
                rt.consecutive_failures += 1

                try:
                    from ui.health_checker import DashboardStatsManager
                    DashboardStatsManager.record_provider_failure(
                        candidate_name,
                        status_cat,
                        clean_msg,
                        latency_ms=rt.last_latency_ms,
                        retry_after=retry_sec,
                    )
                except Exception:
                    pass

                self._record_failure()
                logger.error(
                    "Provider '%s' failed mid-stream after %.3fs: %s.",
                    candidate_name,
                    elapsed,
                    exc,
                    exc_info=True,
                )
                raise AllProvidersFailedError(
                    f"Provider '{candidate_name}' failed while streaming a "
                    "response, after streaming had already begun; fallback is "
                    "not possible mid-stream.",
                    original_exception=exc,
                ) from exc

            elapsed = time.monotonic() - start_time
            lat_ms = round(elapsed * 1000, 1)
            rt.status = "HEALTHY"
            rt.last_latency_ms = lat_ms
            rt.last_success_time = time.time()
            rt.last_error = None
            rt.retry_after_seconds = None
            rt.consecutive_failures = 0
            rt.successful_requests += 1

            try:
                from ui.health_checker import DashboardStatsManager
                DashboardStatsManager.record_provider_success(
                    candidate_name,
                    latency_ms=lat_ms,
                    fallback_used=(idx > 0),
                    primary_failed=candidates[0] if idx > 0 else "",
                )
            except Exception:
                pass

            self._record_success(candidate_name, elapsed)
            logger.info(
                "Provider '%s' completed streaming successfully in %.3fs.",
                candidate_name,
                elapsed,
            )
            return

        self._record_failure()
        raise AllProvidersFailedError(
            "All candidate providers failed before streaming could begin.",
            original_exception=last_error,
        )

    def _get_or_create_runtime_status(self, provider_name: str) -> ProviderRuntimeStatus:
        """Get or initialize the real-time status record for a provider."""
        with self._lock:
            if provider_name not in self._runtime_status:
                self._runtime_status[provider_name] = ProviderRuntimeStatus(name=provider_name)
            return self._runtime_status[provider_name]

    def _classify_error(self, exc: Exception) -> tuple[str, str, float | None]:
        """Classify exception into standard status, clean message, and optional retry delay."""
        status, clean, retry = classify_provider_error(exc)
        err_lower = str(exc).lower()
        if "quota" in err_lower or "insufficient_quota" in err_lower or "exceeded your current quota" in err_lower:
            return "QUOTA EXCEEDED", "API Quota Exceeded", retry
        if status == "RATE_LIMITED":
            return "RATE LIMITED", clean, retry
        if status == "AUTH_ERROR":
            auth_msg = "Invalid API key provided" if ("api key" in err_lower or "unauthorized" in err_lower) else clean
            return "ERROR", auth_msg, retry
        if status == "NETWORK_ERROR":
            return "OFFLINE", clean, retry
        return status, clean, retry

    def get_runtime_status(self, provider_name: str) -> ProviderRuntimeStatus | None:
        """Return real-time diagnostic status for a specific provider."""
        with self._lock:
            return self._runtime_status.get(provider_name)

    def get_all_runtime_statuses(self) -> dict[str, ProviderRuntimeStatus]:
        """Return real-time diagnostic status for all registered providers."""
        with self._lock:
            return dict(self._runtime_status)

    # -------------------------------------------------------------------
    # Statistics
    # -------------------------------------------------------------------

    def statistics(self) -> dict[str, object]:
        """Return a snapshot of current runtime usage statistics.

        Returns:
            A dictionary containing total requests, successful
            requests, failed requests, per-provider usage counts, the
            most recently used provider, and the average response
            time in seconds.
        """
        with self._lock:
            return {
                "total_requests": self._statistics.total_requests,
                "successful_requests": self._statistics.successful_requests,
                "failed_requests": self._statistics.failed_requests,
                "provider_usage_count": dict(self._statistics.provider_usage_count),
                "last_provider_used": self._statistics.last_provider_used,
                "average_response_time_seconds": self._statistics.average_response_time_seconds,
            }

    def reset_statistics(self) -> None:
        """Reset all runtime usage statistics to their initial state."""
        with self._lock:
            self._statistics = ProviderStatistics()
            logger.info("Provider manager statistics have been reset.")

    def _record_request_start(self) -> None:
        """Record that a new request has been attempted."""
        with self._lock:
            self._statistics.total_requests += 1

    def _record_success(self, provider_name: str, elapsed_seconds: float) -> None:
        """Record a successful request fulfilled by a specific provider.

        Args:
            provider_name: The name of the provider that fulfilled the
                request.
            elapsed_seconds: The time taken to fulfill the request, in
                seconds.
        """
        with self._lock:
            self._statistics.successful_requests += 1
            self._statistics.total_response_time_seconds += elapsed_seconds
            self._statistics.provider_usage_count[provider_name] = (
                self._statistics.provider_usage_count.get(provider_name, 0) + 1
            )
            self._statistics.last_provider_used = provider_name
            logger.debug(
                "Statistics updated after successful request via '%s'.", provider_name
            )

    def _record_failure(self) -> None:
        """Record a request for which every candidate provider failed."""
        with self._lock:
            self._statistics.failed_requests += 1
            logger.debug("Statistics updated after a fully failed request.")

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _resolve_candidates(
        self,
        task_type: TaskType,
        mode: SelectionMode,
        provider_name: str | None,
    ) -> tuple[str, ...]:
        """Resolve the ordered list of candidate provider names for a request.

        Args:
            task_type: The kind of task to optimize routing for, used
                only when ``mode="auto"``.
            mode: ``"auto"`` or ``"manual"``.
            provider_name: The provider to use when ``mode="manual"``.

        Returns:
            An ordered tuple of provider names to attempt, in order.

        Raises:
            AIProviderError: If ``mode="manual"`` and ``provider_name``
                is not provided, or if ``mode`` is not a recognized
                value.
            ProviderNotFoundError: If ``mode="manual"`` and
                ``provider_name`` does not refer to a registered
                provider.
        """
        if mode == "manual":
            if provider_name is None:
                raise AIProviderError("Manual provider selection requires a provider_name.")
            if not self.provider_exists(provider_name):
                raise ProviderNotFoundError(
                    f"No provider is registered under the name '{provider_name}'."
                )
            return (provider_name,)

        if mode == "auto":
            return self._router.priority_order(task_type)

        raise AIProviderError(f"Unknown provider selection mode '{mode}'.")

    def _normalize_task_type(self, task_type: TaskType | str) -> TaskType:
        """Normalize a task type argument into a :class:`TaskType` member.

        Args:
            task_type: A :class:`TaskType` member, or its string value.

        Returns:
            The corresponding :class:`TaskType` member.

        Raises:
            AIProviderError: If ``task_type`` does not correspond to
                any known :class:`TaskType` value.
        """
        if isinstance(task_type, TaskType):
            return task_type
        try:
            return TaskType(task_type)
        except ValueError as exc:
            raise AIProviderError(
                f"Unknown task_type '{task_type}'.", original_exception=exc
            ) from exc


__all__ = [
    "ProviderManager",
    "ProviderStatistics",
    "TaskType",
    "ProviderNotFoundError",
    "DuplicateProviderError",
    "AllProvidersFailedError",
]
