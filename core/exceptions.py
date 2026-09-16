"""Centralized exception hierarchy for NOVA.

This module defines every custom exception used across NOVA. All
exceptions inherit, directly or indirectly, from a single base class,
:class:`NovaError`. This allows calling code to catch errors at
whatever level of granularity is appropriate: a specific provider
error (e.g. :class:`GeminiError`), a category of error (e.g.
:class:`AIProviderError`), or any NOVA-originated error at all (via
:class:`NovaError`).

Every exception in this module accepts an optional human-readable
message and an optional reference to the original exception that
caused it, so that error context is never silently lost as
exceptions propagate up through NOVA's layers.

No other module should define its own top-level exception classes
for concerns already represented here. New error categories should
be added to this hierarchy so the whole application shares one
consistent vocabulary of failure modes.
"""

from __future__ import annotations


class NovaError(Exception):
    """Base exception for all errors raised by NOVA.

    Every custom exception in NOVA inherits from this class, either
    directly or through an intermediate category exception. This
    makes it possible to catch any NOVA-originated error with a
    single ``except NovaError:`` clause.

    Attributes:
        message: A human-readable description of the error.
        original_exception: The underlying exception that caused
            this error, if any. Preserved so that the original
            traceback and context are never lost when an error is
            translated into a NOVA-specific exception type.
    """

    default_message: str = "An unspecified error occurred in NOVA."

    def __init__(
        self,
        message: str | None = None,
        *,
        original_exception: BaseException | None = None,
    ) -> None:
        """Initialize a NOVA exception.

        Args:
            message: A human-readable description of the error. If
                ``None``, the class-level ``default_message`` is
                used instead.
            original_exception: The underlying exception that
                triggered this error, if this exception is being
                raised in response to another (e.g. via
                ``raise NovaError(...) from original_exception``).
        """
        self.message = message or self.default_message

        self.original_exception = original_exception

        super().__init__(self.message)

    def __str__(self) -> str:

        """Return the human-readable error message."""

        return self.message

class ConfigurationError(NovaError):
    """Raised when NOVA's configuration is invalid, missing, or malformed.

    This covers general configuration failures encountered outside
    of the initial settings-loading process handled in
    ``config.settings`` (for example, configuration values that
    are only validated lazily, at the point of use, by a specific
    module).
    """

    default_message: str = "NOVA encountered an invalid or missing configuration value."


class AIProviderError(NovaError):
    """Raised when an AI provider fails to fulfill a request.

    This is the general category exception for all AI provider
    failures. Calling code that wants to react to *any* provider
    failure (for example, to trigger fallback to a different
    provider) should catch this class rather than each specific
    provider exception individually.
    """

    default_message: str = "An AI provider failed to fulfill a request."


class GeminiError(AIProviderError):
    """Raised when a request to Google Gemini fails.

    This includes authentication failures, rate limiting, malformed
    requests, and unexpected responses from the Gemini API.
    """

    default_message: str = "Google Gemini failed to fulfill a request."


class GroqError(AIProviderError):
    """Raised when a request to Groq fails.

    This includes authentication failures, rate limiting, malformed
    requests, and unexpected responses from the Groq API.
    """

    default_message: str = "Groq failed to fulfill a request."


class OpenRouterError(AIProviderError):
    """Raised when a request to OpenRouter fails.

    This includes authentication failures, rate limiting, malformed
    requests, and unexpected responses from the OpenRouter API.
    """

    default_message: str = "OpenRouter failed to fulfill a request."


class CerebrasError(AIProviderError):
    """Raised when a request to Cerebras fails.

    This includes authentication failures, rate limiting, malformed
    requests, and unexpected responses from the Cerebras API.
    """

    default_message: str = "Cerebras failed to fulfill a request."


class VoiceError(NovaError):
    """Raised when a voice-related operation fails.

    This is the general category exception for all voice subsystem
    failures, including speech recognition, text-to-speech, and
    wake-word detection.
    """

    default_message: str = "A voice subsystem operation failed."


class SpeechRecognitionError(VoiceError):
    """Raised when NOVA fails to transcribe spoken audio into text.

    This includes failures in the underlying recognition engine,
    unintelligible or empty audio input, and unsupported audio
    formats.
    """

    default_message: str = "NOVA failed to recognize speech from the provided audio."


class TextToSpeechError(VoiceError):
    """Raised when NOVA fails to synthesize speech from text.

    This includes failures from the underlying text-to-speech
    engine (such as ElevenLabs), unsupported voice configurations,
    and audio generation failures.
    """

    default_message: str = "NOVA failed to synthesize speech from text."


class WakeWordError(VoiceError):
    """Raised when NOVA's wake-word detection subsystem fails.

    This includes failures to initialize the wake-word engine,
    unsupported wake-word models, and runtime detection failures.
    """

    default_message: str = "NOVA's wake-word detection subsystem failed."


class VisionError(NovaError):
    """Raised when a vision or image-processing operation fails.

    This covers failures in image capture, image analysis, and any
    future visual perception capabilities NOVA may support.
    """

    default_message: str = "A vision subsystem operation failed."


class MemorySystemError(NovaError):
    """Raised when NOVA's memory or personalization subsystem fails.

    This covers failures to store, retrieve, or update persistent
    user context, conversation history, embeddings, and long-term
    personalization data used by NOVA.
    """

    default_message: str = "NOVA's memory subsystem encountered an error."


class PluginError(NovaError):
    """Raised when a plugin fails to load, initialize, or execute.

    This covers failures within NOVA's future plugin system,
    including missing plugin dependencies, malformed plugin
    manifests, and runtime errors raised by plugin code.
    """

    default_message: str = "A plugin encountered an error."


class AutomationError(NovaError):
    """Raised when an automated task or routine fails.

    This covers failures within NOVA's task automation and
    proactive-assistance capabilities, including scheduling
    failures and failed automation actions.
    """

    default_message: str = "An automation task failed to complete."


class SearchError(NovaError):
    """Raised when a web search operation fails.

    This covers failures from search-grounding integrations (such as
    Tavily), including request failures, rate limiting, and
    malformed or empty search results.
    """

    default_message: str = "A web search operation failed."


class NetworkError(NovaError):
    """Raised when a network-level operation fails.

    This covers general connectivity failures, timeouts, and DNS
    resolution failures that are not specific to any single provider
    or integration.
    """

    default_message: str = "A network operation failed."


class AuthenticationError(NovaError):
    """Raised when authentication with an external service fails.

    This covers failures such as invalid or expired credentials,
    failed OAuth token exchanges, and rejected API keys.
    """

    default_message: str = "Authentication with an external service failed."


class PermissionDeniedError(NovaError):
    """Raised when an operation is denied due to insufficient permissions.

    This covers both external authorization failures (such as an
    OAuth scope that was not granted) and internal permission checks
    within NOVA.
    """

    default_message: str = "The requested operation was denied due to insufficient permissions."


class FileOperationError(NovaError):
    """Raised when a file system operation fails.

    This covers failures to read, write, create, or delete files,
    including permission errors and missing paths, encountered
    outside of the logging subsystem's own error handling.
    """

    default_message: str = "A file system operation failed."


class DatabaseError(NovaError):
    """Raised when a database operation fails.

    This covers failures such as failed connections, failed queries,
    and data integrity violations within NOVA's future persistence
    layer.
    """

    default_message: str = "A database operation failed."


class StartupError(NovaError):
    """Raised when NOVA fails to start up correctly.

    This covers failures during application initialization that are
    not already captured by a more specific exception, such as
    failures wiring together core subsystems before NOVA becomes
    ready to handle requests.
    """

    default_message: str = "NOVA failed to start up correctly."


# =============================================================================
# AGENT RUNTIME ERROR HIERARCHY (PHASE A)
# =============================================================================


class AgentRuntimeError(NovaError):
    """Base exception for all agent runtime and autonomous task failures."""

    default_message: str = "An error occurred within the Agent Runtime."


class CapabilityUnavailableError(AgentRuntimeError):
    """Raised when a requested capability is not registered or unavailable."""

    default_message: str = "The requested capability is not available or registered."


class PermissionRequiredError(AgentRuntimeError, PermissionDeniedError):
    """Raised when an autonomous step requires permissions that have not been granted."""

    default_message: str = (
        "The requested agent operation requires permissions that have not been granted."
    )


class DependencyMissingError(AgentRuntimeError):
    """Raised when a task step requires an external dependency or tool that is not installed."""

    default_message: str = "A required dependency for the task is missing on the system."


class ActionExecutionError(AgentRuntimeError):
    """Raised when a capability handler raises an unhandled error during execution."""

    default_message: str = "An error occurred during capability execution."


class VerificationFailedError(AgentRuntimeError):
    """Raised when post-action verification fails to confirm the expected effect."""

    default_message: str = "Post-action verification failed to confirm the expected outcome."


class ObservationTimeoutError(AgentRuntimeError):
    """Raised when environment or screen observation fails to return within the timeout budget."""

    default_message: str = "Observation of system or screen state timed out."


class PolicyViolationError(AgentRuntimeError):
    """Raised when an action violates safety policies (e.g. sandbox or sensitive web action)."""

    default_message: str = "The requested action violates an active safety policy."


class TaskBudgetExceededError(AgentRuntimeError):
    """Raised when a task exceeds its allocated duration, step count, or retry budget."""

    default_message: str = "The task exceeded its allocated execution budget."


class AmbiguousGoalError(AgentRuntimeError):
    """Raised when a user goal or target reference cannot be resolved unambiguously."""

    default_message: str = (
        "The goal or target reference is ambiguous and requires user clarification."
    )



__all__ = [
    "NovaError",
    "ConfigurationError",
    "AIProviderError",
    "GeminiError",
    "GroqError",
    "OpenRouterError",
    "CerebrasError",
    "VoiceError",
    "SpeechRecognitionError",
    "TextToSpeechError",
    "WakeWordError",
    "VisionError",
    "MemorySystemError",
    "PluginError",
    "AutomationError",
    "SearchError",
    "NetworkError",
    "AuthenticationError",
    "PermissionDeniedError",
    "FileOperationError",
    "DatabaseError",
    "StartupError",
    "AgentRuntimeError",
    "CapabilityUnavailableError",
    "PermissionRequiredError",
    "DependencyMissingError",
    "ActionExecutionError",
    "VerificationFailedError",
    "ObservationTimeoutError",
    "PolicyViolationError",
    "TaskBudgetExceededError",
    "AmbiguousGoalError",
]

