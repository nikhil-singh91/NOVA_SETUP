"""Global service registry for NOVA.

This module provides the single, shared location where every NOVA
subsystem — AI providers, memory, voice, vision, plugins, automation,
and any future subsystem — registers exactly one live instance of
itself, so that other parts of the application can retrieve it by
name without importing that subsystem's module directly.

This decoupling is what allows ``core`` to remain free of
provider-specific or subsystem-specific imports: ``core/registry.py``
knows nothing about Gemini, Groq, memory storage, or voice synthesis.
It only knows how to hold, retrieve, and remove arbitrary named
objects safely. The subsystems themselves are responsible for
constructing their own instance and calling :meth:`ServiceRegistry.register`
during application startup (for example, from ``main.py`` or a future
bootstrap module).

Example:
    from core.registry import registry
    from providers.gemini_provider import GeminiProvider

    registry.register("gemini_provider", GeminiProvider())
    ...
    provider = registry.get("gemini_provider")

Thread Safety:
    All registry operations are guarded by a single
    :class:`threading.RLock`, making the registry safe to read from
    and write to concurrently from multiple threads. A reentrant lock
    is used specifically so that a single thread can safely call one
    registry method from within another (for example, checking
    :meth:`exists` before calling :meth:`register`) without
    deadlocking itself.
"""

from __future__ import annotations

import threading
from typing import Final

from core.exceptions import NovaError
from core.logger import get_logger

logger = get_logger(__name__)


class ServiceRegistry:
    """A thread-safe, in-memory registry of named service instances.

    The registry stores exactly one instance per service name. It is
    intentionally unopinionated about what a "service" is: any
    Python object can be registered, retrieved, and removed by name.
    This keeps the registry itself free of dependencies on any
    specific subsystem.

    Attributes:
        _services: The internal mapping of service name to the
            registered service instance.
        _lock: A reentrant lock guarding all access to ``_services``.
    """

    def __init__(self) -> None:
        """Initialize an empty service registry."""
        self._services: dict[str, object] = {}
        self._lock: threading.RLock = threading.RLock()

    def register(self, name: str, service: object) -> None:
        """Register a service instance under a unique name.

        Args:
            name: The unique identifier under which to register the
                service (for example, ``"gemini_provider"``).
            service: The service instance to register.

        Raises:
            NovaError: If a service is already registered under
                ``name``. The registry rejects duplicate registrations
                rather than silently overwriting them, since an
                accidental duplicate registration usually indicates a
                startup ordering bug elsewhere in the application.
        """
        with self._lock:
            if name in self._services:
                raise NovaError(
                    f"Cannot register service '{name}': a service with this "
                    "name is already registered."
                )
            self._services[name] = service
            logger.info("Service '%s' registered (%s).", name, type(service).__name__)

    def get(self, name: str) -> object:
        """Retrieve a previously registered service instance by name.

        Args:
            name: The unique identifier of the service to retrieve.

        Returns:
            The service instance registered under ``name``.

        Raises:
            NovaError: If no service is registered under ``name``.
        """
        with self._lock:
            if name not in self._services:
                raise NovaError(f"No service is registered under the name '{name}'.")
            return self._services[name]

    def remove(self, name: str) -> None:
        """Remove a previously registered service instance by name.

        Args:
            name: The unique identifier of the service to remove.

        Raises:
            NovaError: If no service is registered under ``name``.
        """
        with self._lock:
            if name not in self._services:
                raise NovaError(
                    f"Cannot remove service '{name}': no service is registered "
                    "under this name."
                )
            del self._services[name]
            logger.info("Service '%s' removed from the registry.", name)

    def exists(self, name: str) -> bool:
        """Check whether a service is currently registered under a name.

        Args:
            name: The unique identifier to check.

        Returns:
            ``True`` if a service is registered under ``name``,
            ``False`` otherwise.
        """
        with self._lock:
            return name in self._services

    def clear(self) -> None:
        """Remove every registered service from the registry.

        This is intended primarily for test teardown and controlled
        application shutdown, where all subsystems must be
        de-registered at once.
        """
        with self._lock:
            removed_count = len(self._services)
            self._services.clear()
            logger.info("Service registry cleared (%d service(s) removed).", removed_count)

    def list_services(self) -> tuple[str, ...]:
        """List the names of every currently registered service.

        Returns:
            A tuple of registered service names. The tuple is a
            snapshot taken under the registry's lock, so it remains
            safe to iterate even if other threads later modify the
            registry.
        """
        with self._lock:
            return tuple(self._services.keys())


registry: Final[ServiceRegistry] = ServiceRegistry()
"""The single, shared service registry instance used across all of NOVA."""


__all__ = [
    "ServiceRegistry",
    "registry",
]
