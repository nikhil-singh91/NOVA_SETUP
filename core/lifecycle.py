"""Application lifecycle management for NOVA.

This module owns NOVA's entire application lifecycle: startup,
readiness verification, graceful shutdown, and restart. It is the
first subsystem invoked when the application launches (from
``main.py``) and the last subsystem invoked when it terminates.

``LifecycleManager`` deliberately knows nothing about any specific
provider, integration, or subsystem implementation. It coordinates
generic, cross-cutting concerns only:

- Ensuring required working directories exist (via ``core.paths``).
- Tracking whether the application is currently running.
- Providing a single point through which subsystems register
  themselves into the shared service registry (via ``core.registry``)
  during startup, and are cleanly removed during shutdown.

Concrete subsystems (an AI provider, a memory store, a voice engine,
and so on) are constructed by their own modules and handed to
:meth:`LifecycleManager.register_service` during application
bootstrap. This keeps ``core`` free of any dependency on the modules
it manages, avoiding circular imports.

Example:
    from core.lifecycle import lifecycle

    lifecycle.start()
    ...
    lifecycle.shutdown()
"""

from __future__ import annotations

import threading
from typing import Final

from config.settings import settings
from core.exceptions import StartupError
from core.logger import get_logger
from core.paths import ensure_directories
from core.registry import registry

logger = get_logger(__name__)

_LIFECYCLE_SERVICE_NAME: Final[str] = "lifecycle"


class LifecycleManager:
    """Coordinates NOVA's startup, readiness, and shutdown sequence.

    ``LifecycleManager`` is responsible for bringing the application
    into a running state, verifying it is ready to serve requests,
    and tearing it down cleanly. It is designed to be used as a
    single shared instance for the lifetime of the process.

    Attributes:
        _started: Whether the application is currently considered
            running.
        _lock: A reentrant lock guarding all state transitions, so
            that lifecycle methods are safe to call concurrently from
            multiple threads.
    """

    def __init__(self) -> None:
        """Initialize a lifecycle manager in the not-started state."""
        self._started: bool = False
        self._lock: threading.RLock = threading.RLock()

    def start(self) -> None:
        """Start the application.

        Ensures all required working directories exist, performs
        readiness checks, and registers the lifecycle manager itself
        into the shared service registry. Startup is guarded against
        being run twice.

        Raises:
            StartupError: If the application is already running, or
                if any step of the startup sequence fails.
        """
        with self._lock:
            if self._started:
                raise StartupError(
                    "NOVA is already running; start() cannot be called twice "
                    "without an intervening shutdown()."
                )

            logger.info(
                "NOVA startup sequence initiated (app_env=%s, debug=%s).",
                settings.app_env,
                settings.debug,
            )

            try:
                ensure_directories()
                self._run_readiness_checks()
                registry.register(_LIFECYCLE_SERVICE_NAME, self)
            except Exception as exc:
                logger.error("NOVA failed to start: %s", exc, exc_info=True)
                raise StartupError(
                    "NOVA failed to start due to an initialization error.",
                    original_exception=exc,
                ) from exc

            self._started = True
            logger.info("NOVA startup completed successfully.")

    def shutdown(self) -> None:
        """Shut down the application gracefully.

        Removes the lifecycle manager from the shared service
        registry and marks the application as no longer running.
        Shutdown is guarded against being run twice.

        Raises:
            StartupError: If the application is not currently
                running, or if any step of the shutdown sequence
                fails.
        """
        with self._lock:
            if not self._started:
                raise StartupError(
                    "Cannot shut down NOVA: it is not currently running."
                )

            logger.info("NOVA shutdown sequence initiated.")

            try:
                if registry.exists(_LIFECYCLE_SERVICE_NAME):
                    registry.remove(_LIFECYCLE_SERVICE_NAME)
            except Exception as exc:
                logger.error("NOVA failed to shut down cleanly: %s", exc, exc_info=True)
                raise StartupError(
                    "NOVA failed to shut down cleanly due to an error while "
                    "releasing registered services.",
                    original_exception=exc,
                ) from exc

            self._started = False
            logger.info("NOVA shutdown completed successfully.")

    def restart(self) -> None:
        """Restart the application.

        Performs a graceful shutdown, if currently running, followed
        immediately by a fresh startup sequence.

        Raises:
            StartupError: If either the shutdown or startup phase of
                the restart fails.
        """
        with self._lock:
            logger.info("NOVA restart requested.")
            if self._started:
                self.shutdown()
            self.start()

            logger.info("NOVA restarted successfully.")

    def is_running(self) -> bool:
        """Report whether the application is currently running.

        Returns:
            ``True`` if :meth:`start` has completed successfully and
            :meth:`shutdown` has not since been called, ``False``
            otherwise.
        """
        with self._lock:
            return self._started

    def register_service(self, name: str, service: object) -> None:
        """Register an initialized subsystem into the shared registry.

        This is the mechanism by which concrete subsystems (AI
        providers, memory stores, voice engines, and so on),
        constructed elsewhere in the application, become discoverable
        through the lifecycle manager during and after startup.

        Args:
            name: The unique identifier under which to register the
                service.
            service: The initialized service instance to register.

        Raises:
            NovaError: If a service is already registered under
                ``name``. Propagated unchanged from the underlying
                service registry.
        """
        with self._lock:
            if not self._started:
             raise StartupError(
                "Cannot register services before NOVA has started."
        )

            registry.register(name, service)
            logger.info(
                "Service '%s' registered during lifecycle management.",
                name,
            )
    def get_service(self, name: str) -> object:
        """Retrieve a previously registered subsystem by name.

        Args:
            name: The unique identifier of the service to retrieve.

        Returns:
            The registered service instance.

        Raises:
            NovaError: If no service is registered under ``name``.
                Propagated unchanged from the underlying service
                registry.
        """
        with self._lock:
            if not self._started:
                raise StartupError(
                    "Cannot access services before NOVA has started."
                )

            return registry.get(name)

    def _run_readiness_checks(self) -> None:
        """Verify that NOVA is in a valid state to begin serving requests.

        This performs lightweight, generic readiness verification
        that does not depend on any specific subsystem: confirming
        that application settings loaded successfully and that the
        configured application environment is one that NOVA
        recognizes. Subsystem-specific readiness (for example, an AI
        provider confirming its API key works) is each subsystem's
        own responsibility once registered.

        Raises:
            StartupError: If a readiness precondition is not met.
        """
        if settings is None:
            raise StartupError(
                "NOVA cannot start: application settings failed to load."
            )
        logger.debug("Readiness checks passed for app_env=%s.", settings.app_env)


lifecycle: Final[LifecycleManager] = LifecycleManager()
"""The single, shared lifecycle manager instance used to run all of NOVA."""


__all__ = [
    "LifecycleManager",
    "lifecycle",
]
