"""NOVA's application entry point and orchestrator.

This module is NOVA's orchestrator, not its brain. Every subsystem it
imports already owns its own logic (Providers decide how to talk to
an LLM, Memory decides how to store facts, Personality decides tone
and content, Voice decides how to listen and speak). This module's
job is limited to exactly what the approved architecture document
assigns to it:

- The startup sequence and registry wiring.
- The Companion Startup Flow (a personality-generated greeting that
  references the last active project and the previous session).
- The main event loop (a simple state machine driven by either typed
  console input or a wake-word-triggered voice turn).
- The conversation pipeline (one turn: analyze, retrieve context,
  build a prompt, call a provider, decide what to remember, respond).
- Activity Tracking (a small, ephemeral, in-process runtime state
  bundle — current project/task/topic — that is never persisted,
  except for the one deliberate breadcrumb written at shutdown).
- The Event Bus (a dependency-free publish mechanism for a future UI).
- The Companion Shutdown Flow (a personality-generated farewell,
  followed by graceful, per-component teardown).
- Signal handling.

Known Gaps (deliberately not invented — see accompanying explanation):
    - ``SessionContextManager`` (short-term conversational memory and
      reference resolution) does not exist as an implemented module.
      The steps of the conversation pipeline where it would be
      consulted are marked with explicit comments; this module does
      not fabricate a substitute.
    - ``config.settings.Settings`` has no Picovoice access-key field,
      so :class:`~voice.wake_word.WakeWordConfig` is constructed with
      ``access_key=None`` here, which causes wake-word initialization
      to fail cleanly and non-fatally until that field is added.
"""

from __future__ import annotations

import queue
import re
import signal
import sys
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import numpy as np
from core.exceptions import MemorySystemError as NovaMemoryError
from core.exceptions import (
    SpeechRecognitionError,
    TextToSpeechError,
)
from core.lifecycle import lifecycle
from core.logger import get_logger, setup_logging
from mac_control import MacControlManager
from memory.memory_manager import MemoryCategory, MemoryManager
from memory.vector_store import VectorStore
from personality.emotion_engine import ConversationAnalysis, ConversationMode, EmotionEngine
from personality.system_prompt import (
    DuplicateProfileError,
    ProfileName,
    ProfileNotFoundError,
    PromptBuildContext,
    PromptProfile,
    SystemPromptError,
    SystemPromptManager,
)
from providers.provider_manager import AllProvidersFailedError, ProviderManager, TaskType
from voice.commands import CommandRecognizer, VoiceCommandRouter
from voice.speech_to_text import SpeechToTextManager
from voice.text_to_speech import TextToSpeechManager

logger = get_logger(__name__)

_BREADCRUMB_KEY = "last_session_summary"
_GREETING_PROFILE_NAME = "greeting"
_FAREWELL_PROFILE_NAME = "farewell"
_TURN_QUEUE_POLL_SECONDS = 0.5

# The shared base sections every default SystemPromptManager profile is built
# from (see personality/system_prompt.py's _BASE_PRE_SECTIONS/_BASE_POST_SECTIONS).
# Used verbatim to compose the two companion-specific profiles registered at
# startup, via the manager's existing, documented register_profile() extension
# point — this is a use of an existing public API, not a new one.
_COMPANION_PROFILE_SECTIONS: tuple[str, ...] = (
    "identity",
    "personality",
    "language",
    "user_profile",
    "memory",
    "conversation",
    "temporal_context",
    "emotion",
    "current_task",
    "provider_context",
    "safety",
    "formatting_rules",
    "custom_instructions",
)


class NovaEvent(str, Enum):
    """The observational events NOVA emits for a future UI to subscribe to.

    Per the architecture document's Principle 7, these events are
    purely observational: no branch of this module's own control flow
    depends on whether any subscriber exists.

    Attributes:
        APPLICATION_STARTED: Emitted once the startup greeting has
            been delivered, immediately before the event loop begins.
        WAKE_WORD_DETECTED: Emitted the instant a wake word is
            detected, before speech recognition begins.
        LISTENING_STARTED: Emitted when this turn's input capture
            begins (voice or text).
        THINKING_STARTED: Emitted once input text for this turn is
            finalized and analysis begins.
        RESPONSE_GENERATED: Emitted once a response has been produced
            successfully.
        SPEAKING_STARTED: Emitted when text-to-speech begins
            synthesizing a response.
        SPEAKING_FINISHED: Emitted when text-to-speech completes (or
            fails) for a response.
        APPLICATION_SHUTDOWN: Emitted at the very start of the
            Companion Shutdown Flow.
    """

    APPLICATION_STARTED = "application_started"
    WAKE_WORD_DETECTED = "wake_word_detected"
    LISTENING_STARTED = "listening_started"
    THINKING_STARTED = "thinking_started"
    RESPONSE_GENERATED = "response_generated"
    SPEAKING_STARTED = "speaking_started"
    SPEAKING_FINISHED = "speaking_finished"
    APPLICATION_SHUTDOWN = "application_shutdown"
    STATE_CHANGED = "state_changed"
    COMMAND_EXECUTED = "command_executed"
    HEALTH_UPDATE = "health_update"
    LISTENING_FINISHED = "listening_finished"
    LISTENING_PARTIAL = "listening_partial"
    SPEECH_INTERRUPTED = "speech_interrupted"


#: The signature every event subscriber must implement: the event that
#: fired, and a payload of event-specific keyword data.
EventHandler = Callable[[NovaEvent, dict[str, Any]], None]


class EventBus:
    """A minimal, dependency-free publish/subscribe mechanism.

    This is the concrete implementation of the architecture document's
    "Event Bus": a generalization of the single-callback pattern
    already used by :meth:`~voice.wake_word.WakeWordManager.start_listening`
    and :meth:`~voice.text_to_speech.TextToSpeechManager.speak_async`,
    extended to support an arbitrary number of subscribers per event.

    Attributes:
        _lock: A reentrant lock guarding the subscriber registry.
        _subscribers: A mapping of event to the list of handlers
            registered for it.
    """

    def __init__(self) -> None:
        """Construct an empty event bus."""
        self._lock: threading.RLock = threading.RLock()
        self._subscribers: dict[NovaEvent, list[EventHandler]] = {}

    def subscribe(self, event: NovaEvent, handler: EventHandler) -> None:
        """Register a handler to be called whenever an event is published.

        Args:
            event: The event to subscribe to.
            handler: The callable to invoke when ``event`` is
                published.
        """
        with self._lock:
            self._subscribers.setdefault(event, []).append(handler)

    def unsubscribe(self, event: NovaEvent, handler: EventHandler) -> None:
        """Remove a previously registered handler.

        Args:
            event: The event to unsubscribe from.
            handler: The handler to remove. A no-op if it is not
                currently registered.
        """
        with self._lock:
            handlers = self._subscribers.get(event)
            if handlers and handler in handlers:
                handlers.remove(handler)

    def publish(self, event: NovaEvent, **payload: Any) -> None:
        """Publish an event to every registered subscriber.

        A failing subscriber is logged and does not prevent the
        remaining subscribers from being notified, and never
        propagates back to the caller — per Principle 7, a broken
        subscriber must never affect NOVA's own behavior.

        Args:
            event: The event being published.
            **payload: Event-specific data passed to each subscriber.
        """
        with self._lock:
            handlers = tuple(self._subscribers.get(event, ()))

        for handler in handlers:
            try:
                handler(event, payload)
            except Exception as exc:  # noqa: BLE001 - a bad subscriber must not affect NOVA
                logger.error(
                    "Event subscriber raised an exception for '%s': %s",
                    event.value,
                    exc,
                    exc_info=True,
                )


@dataclass
class ActivityState:
    """Ephemeral, in-process runtime state tracked only by this module.

    This is explicitly not memory: it is discarded on shutdown, with
    exactly one deliberate exception — a condensed snapshot of it is
    written into durable memory by the Companion Shutdown Flow, to be
    read back by the next run's Companion Startup Flow.

    Attributes:
        current_project: The project currently in focus, if any.
        current_task: A finer-grained current task, if any.
        session_start_time: When this session began.
        last_conversation_topic: A short representation of the most
            recent turn's subject, used to give the next turn's
            prompt-building something concrete to reference.
    """

    current_project: str | None = None
    current_task: str | None = None
    session_start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    last_conversation_topic: str | None = None


@dataclass(frozen=True)
class TurnRequest:
    """A single unit of work for the conversation pipeline.

    Attributes:
        source: Either ``"voice"`` or ``"text"``.
        text: The typed input text, if ``source == "text"``.
        wake_word_result: The detection result that triggered this
            turn, if ``source == "voice"``.
    """

    source: str
    text: str | None = None
    wake_word_result: Any | None = None


class VoiceState(str, Enum):
    INITIALIZE = "INITIALIZE"
    GREETING = "GREETING"
    LISTENING = "LISTENING"
    THINKING = "THINKING"
    SPEAKING = "SPEAKING"
    ERROR = "ERROR"
    SHUTDOWN = "SHUTDOWN"


class VoiceStateManager:
    def __init__(self, event_bus: EventBus) -> None:
        self._state = VoiceState.INITIALIZE
        self._lock = threading.Lock()
        self._event_bus = event_bus

    @property
    def current_state(self) -> VoiceState:
        with self._lock:
            return self._state

    def set_state(self, new_state: VoiceState) -> None:
        with self._lock:
            old_state = self._state
            if old_state == new_state:
                return

            # Transition rules check
            if old_state == VoiceState.SPEAKING and new_state == VoiceState.LISTENING:
                # This transition is now valid and standard!
                pass

            self._state = new_state
            logger.info("Voice state transitioned: %s -> %s", old_state.value, new_state.value)
            self._event_bus.publish(NovaEvent.STATE_CHANGED, old_state=old_state.value, new_state=new_state.value)


class NovaApplication:
    """NOVA's orchestrator: owns startup, the event loop, and shutdown.

    Attributes:
        event_bus: The application-wide event bus.
        activity: The current ephemeral runtime state.
        memory_manager: NOVA's durable memory store, once initialized.
        vector_store: NOVA's semantic memory layer, once initialized.
        provider_manager: NOVA's AI provider orchestrator, once
            initialized.
        system_prompt_manager: NOVA's personality engine, once
            initialized.
        emotion_engine: NOVA's deterministic emotion/mode analyzer.
        stt_manager: NOVA's speech-to-text manager, once constructed.
        tts_manager: NOVA's text-to-speech manager, once constructed.
        wake_word_manager: NOVA's wake-word manager, once constructed.
        voice_available: Whether both speech-to-text and
            text-to-speech successfully initialized.
    """

    def __init__(self) -> None:
        """Construct an application with no subsystems initialized yet."""
        self.event_bus: EventBus = EventBus()
        self.activity: ActivityState = ActivityState()

        self.memory_manager: MemoryManager | None = None
        self.vector_store: VectorStore | None = None
        self.provider_manager: ProviderManager | None = None
        self.system_prompt_manager: SystemPromptManager | None = None
        self.emotion_engine: EmotionEngine | None = None
        self.stt_manager: SpeechToTextManager | None = None
        self.tts_manager: TextToSpeechManager | None = None

        self.state_manager = VoiceStateManager(self.event_bus)
        self.voice_available: bool = False
        self._voice_input_ready: bool = False
        self._voice_output_ready: bool = False
        self._in_conversation_flow = False
        self._voice_turn_queued = False
        self._interruption_event: threading.Event = threading.Event()
        self._interruption_thread: threading.Thread | None = None

        self._shutdown_requested: threading.Event = threading.Event()
        self._turn_queue: queue.Queue[TurnRequest] = queue.Queue()
        self._console_thread: threading.Thread | None = None
        self._manual_provider_override: str | None = None

        self.command_recognizer = CommandRecognizer()
        self.command_router = VoiceCommandRouter(self.command_recognizer)
        self.command_router.register_handler("shutdown", self._execute_local_shutdown)
        self._conversation_history: list[dict[str, str]] = []
        self._current_spoken_text: str = ""

    @property
    def _processing_turn(self) -> bool:
        return self.state_manager.current_state == VoiceState.THINKING

    @_processing_turn.setter
    def _processing_turn(self, value: bool) -> None:
        if value:
            if self.state_manager.current_state != VoiceState.THINKING:
                self.state_manager.set_state(VoiceState.THINKING)
        else:
            if self.state_manager.current_state == VoiceState.THINKING:
                if not self._assistant_speaking:
                    self.state_manager.set_state(VoiceState.LISTENING)

    @property
    def _assistant_speaking(self) -> bool:
        return self.state_manager.current_state == VoiceState.SPEAKING

    @_assistant_speaking.setter
    def _assistant_speaking(self, value: bool) -> None:
        if value:
            self.state_manager.set_state(VoiceState.SPEAKING)
        else:
            if self.state_manager.current_state == VoiceState.SPEAKING:
                self.state_manager.set_state(VoiceState.LISTENING)

    # -------------------------------------------------------------------
    # Top-level orchestration
    # -------------------------------------------------------------------

    def run(self) -> int:
        """Run NOVA end to end: startup, event loop, shutdown.

        Returns:
            A process exit code: ``0`` on a clean run, ``1`` if an
            essential subsystem failed to initialize or the event loop
            exited due to an unrecoverable error.
        """
        try:
            setup_logging()
            lifecycle.start()
            lifecycle.register_service("event_bus", self.event_bus)
            lifecycle.register_service("voice_state_manager", self.state_manager)
        except Exception as exc:
            logger.critical("NOVA failed to start: %s", exc, exc_info=True)
            return 1

        logger.info("NOVA is starting.")

        # Parallel initialization of independent subsystems
        threads = []
        errors = []

        def run_init(func, name):
            try:
                func()
            except Exception as exc:
                logger.critical("Subsystem %s failed to initialize: %s", name, exc, exc_info=True)
                errors.append(exc)

        for func, name in [
            (self._initialize_memory, "memory"),
            (self._initialize_providers, "providers"),
            (self._initialize_personality, "personality"),
            (self._initialize_mac_control, "mac_control")
        ]:
            t = threading.Thread(target=run_init, args=(func, name), daemon=True, name=f"nova-init-{name}")
            t.start()
            threads.append(t)

        for t in threads:
            t.join()

        if errors:
            self._shutdown()
            return 1

        self._initialize_voice()
        self._register_signal_handlers()
        self.state_manager.set_state(VoiceState.LISTENING)

        # Render the startup dashboard console interface
        from ui import TerminalDashboard
        try:
            dashboard = TerminalDashboard()
            dashboard.render()
        except Exception as exc:
            logger.error("Failed to render the terminal dashboard: %s", exc, exc_info=True)

        if self.voice_available:
            self._in_conversation_flow = True
        self._companion_startup_flow()

        self.event_bus.publish(
            NovaEvent.APPLICATION_STARTED,
            voice_available=self.voice_available,
            last_active_project=self.activity.current_project,
        )

        self._start_background_services()
        exit_code = 0

        try:
            self._run_event_loop()
        except Exception as exc:  # noqa: BLE001 - last line of defense for the loop itself
            logger.critical("Fatal error in the main event loop: %s", exc, exc_info=True)
            exit_code = 1
        finally:
            self._shutdown()

        return exit_code



    # -------------------------------------------------------------------
    # Initialization
    # -------------------------------------------------------------------

    def _initialize_memory(self) -> None:
        """Construct and register the Memory subsystem.

        Raises:
            Exception: Propagated if construction fails; Memory is an
                essential subsystem.
        """
        self.memory_manager = MemoryManager()
        lifecycle.register_service("memory_manager", self.memory_manager)

        self.vector_store = VectorStore()
        self.vector_store.initialize()
        lifecycle.register_service("vector_store", self.vector_store)

        try:
            memories = self.memory_manager.list_memories()
            for memory in memories:
                text_val = str(memory.value) if memory.value is not None else ""
                if text_val:
                    self.vector_store.add_document(
                        text=text_val,
                        document_id=memory.id,
                        category=memory.category.value,
                        tags=memory.tags,
                    )
            logger.info("Indexed %d existing memories into VectorStore.", len(memories))
        except Exception as exc:
            logger.error("Failed to populate VectorStore with existing memories: %s", exc)

        logger.info("Memory subsystem initialized.")

    def _initialize_providers(self) -> None:
        """Construct and register the Providers subsystem.

        Raises:
            Exception: Propagated if construction fails; Providers are
                an essential subsystem. Individual provider failures
                are already handled internally by ``ProviderManager``
                and are never fatal here.
        """
        self.provider_manager = ProviderManager()
        self.provider_manager.initialize()
        lifecycle.register_service("provider_manager", self.provider_manager)
        logger.info(
            "Providers subsystem initialized (available: %s).",
            ", ".join(self.provider_manager.get_available_providers()) or "none",
        )

    def _initialize_personality(self) -> None:
        """Construct and register the Personality subsystem.

        Raises:
            Exception: Propagated if construction fails; Personality is
                an essential subsystem, since the conversation pipeline
                always builds a prompt through it.
        """
        self.system_prompt_manager = SystemPromptManager()
        self.system_prompt_manager.initialize()
        self._register_companion_profiles()
        lifecycle.register_service("system_prompt_manager", self.system_prompt_manager)

        self.emotion_engine = EmotionEngine()
        lifecycle.register_service("emotion_engine", self.emotion_engine)

        logger.info("Personality subsystem initialized.")

    def _initialize_mac_control(self) -> None:
        """Construct and register the macOS Control subsystem."""
        self.mac_control_manager = MacControlManager()
        lifecycle.register_service("mac_control_manager", self.mac_control_manager)
        logger.info("macOS Control subsystem initialized.")

    def _register_companion_profiles(self) -> None:
        """Register the greeting and farewell profiles used by the Companion flows.

        Uses :meth:`~personality.system_prompt.SystemPromptManager.register_profile`,
        an existing, documented extension point, rather than modifying
        ``SystemPromptManager`` itself.
        """
        assert self.system_prompt_manager is not None

        greeting_profile = PromptProfile(
            name=_GREETING_PROFILE_NAME,
            description="Generates NOVA's startup greeting.",
            section_names=_COMPANION_PROFILE_SECTIONS,
            focus_instruction=(
                "This is the very start of a session. Greet the user naturally, "
                "referencing the time of day and, if available, what project or "
                "topic was last active, without sounding like a canned script."
            ),
        )
        farewell_profile = PromptProfile(
            name=_FAREWELL_PROFILE_NAME,
            description="Generates NOVA's end-of-session farewell.",
            section_names=_COMPANION_PROFILE_SECTIONS,
            focus_instruction=(
                "This is the end of a session. Say a brief, natural farewell, "
                "optionally referencing what was worked on, without sounding "
                "like a canned script."
            ),
        )

        for profile in (greeting_profile, farewell_profile):
            try:
                self.system_prompt_manager.register_profile(profile)
            except DuplicateProfileError:
                logger.debug("Companion profile '%s' was already registered.", profile.name)

    def _initialize_voice(self) -> None:
        """Construct the Voice subsystem, never treating a failure as fatal.

        Voice is the most optional subsystem in the architecture: a
        missing microphone, a missing optional dependency, or a
        missing Picovoice access key must never prevent the rest of
        NOVA from running.
        """
        self.stt_manager = SpeechToTextManager()
        self.tts_manager = TextToSpeechManager()

        def init_stt():
            try:
                self.stt_manager.initialize()
                self._voice_input_ready = True
            except SpeechRecognitionError as exc:
                logger.warning("Speech-to-text is unavailable: %s", exc)
                self._voice_input_ready = False
            lifecycle.register_service("stt_manager", self.stt_manager)

        def init_tts():
            try:
                self.tts_manager.initialize()
                self._voice_output_ready = True
            except TextToSpeechError as exc:
                logger.warning("Text-to-speech is unavailable: %s", exc)
                self._voice_output_ready = False
            lifecycle.register_service("tts_manager", self.tts_manager)

        t_stt = threading.Thread(target=init_stt, daemon=True, name="nova-init-stt")
        t_tts = threading.Thread(target=init_tts, daemon=True, name="nova-init-tts")
        t_stt.start()
        t_tts.start()
        t_stt.join()
        t_tts.join()

        self.voice_available = self._voice_input_ready and self._voice_output_ready

        logger.info(
            "Voice subsystem initialized (input=%s, output=%s).",
            self._voice_input_ready,
            self._voice_output_ready,
        )

    def _register_signal_handlers(self) -> None:
        """Register SIGINT/SIGTERM handlers that request a graceful shutdown."""

        def _handle_signal(signum: int, _frame: Any) -> None:
            logger.info("Received signal %s; requesting shutdown.", signum)
            self._shutdown_requested.set()

        for signal_name in ("SIGINT", "SIGTERM"):
            signal_number = getattr(signal, signal_name, None)
            if signal_number is None:
                continue
            try:
                signal.signal(signal_number, _handle_signal)
            except (ValueError, OSError) as exc:
                logger.debug("Could not register a handler for %s: %s", signal_name, exc)

    # -------------------------------------------------------------------
    # Companion Startup Flow
    # -------------------------------------------------------------------

    def _companion_startup_flow(self) -> None:
        """Generate and deliver NOVA's startup greeting.

        Implemented as one synthetic conversation turn through the
        same SystemPromptManager -> ProviderManager pipeline a normal
        turn uses, per the architecture document's Principle 8.
        """
        self.state_manager.set_state(VoiceState.GREETING)
        assert self.system_prompt_manager is not None
        assert self.provider_manager is not None

        last_project = self._get_last_active_project()
        breadcrumb = self._read_breadcrumb()
        self.activity.current_project = last_project

        context = PromptBuildContext(
            current_task="Generate a natural, brief startup greeting for the user.",
            current_project=last_project,
            memory_summary=breadcrumb,
        )

        greeting: str
        try:
            prompt_text = self.system_prompt_manager.build_prompt(
                profile=_GREETING_PROFILE_NAME, context=context
            )
            greeting = self.provider_manager.generate_response(
                prompt="Greet me for the start of this session.",
                system_prompt=prompt_text,
                task_type=TaskType.GENERAL,
            )
        except (AllProvidersFailedError, SystemPromptError, ProfileNotFoundError) as exc:
            logger.warning(
                "Could not generate a startup greeting (%s); using a fallback.", exc
            )
            greeting = "NOVA is online."

        self.event_bus.publish(NovaEvent.RESPONSE_GENERATED, text=greeting, provider=None)
        self._deliver_response(greeting, turn_id="startup")

    def _get_last_active_project(self) -> str | None:
        """Retrieve the most recently updated project from durable memory.

        Returns:
            The most recently updated project's value (or key, if the
            value is empty), or ``None`` if no project memories exist
            or memory could not be read.
        """
        if self.memory_manager is None:
            return None
        try:
            entries = self.memory_manager.get_by_category(MemoryCategory.PROJECTS)
        except NovaMemoryError as exc:
            logger.warning("Could not read project memories: %s", exc)
            return None

        if not entries:
            return None

        latest_entry = max(entries, key=lambda entry: entry.updated_at)
        return str(latest_entry.value) if latest_entry.value else latest_entry.key

    def _read_breadcrumb(self) -> str | None:
        """Read the session-summary breadcrumb left by the previous run.

        Returns:
            The breadcrumb's stored value, or ``None`` if none exists
            or memory could not be read.
        """
        if self.memory_manager is None:
            return None
        try:
            results = self.memory_manager.search_memory(query=_BREADCRUMB_KEY, exact_key=True)
        except NovaMemoryError as exc:
            logger.warning("Could not read the session breadcrumb: %s", exc)
            return None

        if not results:
            return None
        return str(results[0].value)

    def _write_breadcrumb(self, summary: str) -> None:
        """Write (or overwrite) the session-summary breadcrumb for the next run.

        ``MemoryManager`` has no upsert-by-key operation, so this
        searches for an existing breadcrumb entry and updates it if
        found, adding a new one only the first time.

        Args:
            summary: The breadcrumb text to store.
        """
        if self.memory_manager is None:
            return
        try:
            existing = self.memory_manager.search_memory(query=_BREADCRUMB_KEY, exact_key=True)
            if existing:
                self.memory_manager.update_memory(existing[0].id, value=summary)
            else:
                self.memory_manager.add_memory(
                    category=MemoryCategory.CONVERSATIONS,
                    key=_BREADCRUMB_KEY,
                    value=summary,
                    importance=2,
                    tags=("session_breadcrumb",),
                )
        except NovaMemoryError as exc:
            logger.warning("Could not write the session breadcrumb: %s", exc)

    # -------------------------------------------------------------------
    # Background services and the event loop
    # -------------------------------------------------------------------

    def _start_background_services(self) -> None:
        """Start the console input reader and kick off the voice conversation loop."""
        self._console_thread = threading.Thread(
            target=self._console_input_loop,
            name="nova-console-input",
            daemon=True,
        )
        self._console_thread.start()

        if self.voice_available:
            self._in_conversation_flow = True

    def _console_input_loop(self) -> None:
        """Continuously read lines of typed input and enqueue them as turns.

        Runs on a dedicated daemon thread so that blocking on
        ``input()`` never prevents the main thread from processing
        wake-word-triggered turns or responding to shutdown requests.
        """
        while not self._shutdown_requested.is_set():
            try:
                line = input()
            except EOFError:
                break

            stripped = line.strip()
            if not stripped:
                continue

            if stripped.lower() in {"exit", "quit"}:
                self._shutdown_requested.set()
                break

            if stripped.lower().startswith("/provider "):
                self._manual_provider_override = stripped[len("/provider ") :].strip()
                print(f"(Next response will use provider: {self._manual_provider_override})")
                continue

            self._processing_turn = True
            self._turn_queue.put(TurnRequest(source="text", text=stripped))


            # <<< INSERT NEW FUNCTION HERE >>>



    def _run_event_loop(self) -> None:
        """Run the main event loop until a shutdown is requested.

        Consumes exactly one :class:`TurnRequest` at a time from the
        turn queue, guaranteeing only one conversation turn is ever in
        flight, regardless of whether it was triggered by the console
        thread or the wake-word listener thread.
        """
        while not self._shutdown_requested.is_set():
            try:
                request = self._turn_queue.get(timeout=_TURN_QUEUE_POLL_SECONDS)
            except queue.Empty:
                continue
            self._process_turn(request)

    # -------------------------------------------------------------------
    # Conversation pipeline
    # -------------------------------------------------------------------

    def _process_turn(self, request: TurnRequest) -> None:
        """Run one full conversation turn.

        Args:
            request: The triggering request (voice or text).
        """
        if self._assistant_speaking:
            logger.info("Interrupting active speech for new turn.")
            if self.tts_manager is not None:
                self.tts_manager.stop(clear_queue=True)
            self._assistant_speaking = False

        turn_id = uuid.uuid4().hex[:8]
        self._processing_turn = True
        logger.info("[turn-%s] Turn started (source=%s).", turn_id, request.source)
        if request.source == "voice":
            self._voice_turn_queued = False

        try:
            input_text = self._resolve_turn_input(request, turn_id)
            if input_text is None:
                return

            self._last_turn_input = input_text

            if self.command_router.route(input_text):
                return

            # Intercept and process macOS Control actions locally
            mac_result = self.mac_control_manager.process_input(input_text)
            if mac_result is not None:
                voice_reply = self.mac_control_manager.get_voice_response(mac_result)
                self._deliver_response(voice_reply, turn_id)
                return

            # NOTE: SessionContextManager (architecture §3) does not yet exist
            # as an implemented module. Reference resolution ("that one",
            # "continue") is therefore not applied; input_text is used exactly
            # as received from Voice or the console.
            resolved_text = input_text

            self._current_turn_source = request.source
            analysis = self.emotion_engine.analyze_text(resolved_text)  # type: ignore[union-attr]

            memory_summary = self._build_memory_summary(resolved_text)
            task_type = self._map_mode_to_task_type(analysis.detected_mode)
            profile_name = self._map_mode_to_profile(analysis.detected_mode)
            active_provider_name = self._peek_active_provider(task_type)

            self.event_bus.publish(NovaEvent.THINKING_STARTED, text=resolved_text)

            if request.source == "voice":
                print("====================================================")
                print("🧠 NOVA THINKING...")
                print("====================================================")

            context = PromptBuildContext(
                memory_summary=memory_summary,
                current_project=self.activity.current_project,
                current_task=self.activity.current_task,
                emotion=analysis.emotion_description,
                current_provider=active_provider_name,
                voice_mode=(request.source == "voice"),
            )

            from ui.health_checker import DashboardStatsManager
            DashboardStatsManager.update("active_provider", active_provider_name or "Gemini")
            DashboardStatsManager.update("last_transcript", resolved_text)

            gen_start = time.monotonic()
            response_text = self._generate_response(
                resolved_text, context, profile_name, task_type, turn_id
            )
            gen_elapsed = time.monotonic() - gen_start
            DashboardStatsManager.update("latency", f"{gen_elapsed:.2f}s")

            if response_text is None:
                return

            tokens_estimate = len(resolved_text.split()) + len(response_text.split())
            DashboardStatsManager.update("tokens", str(int(tokens_estimate * 1.3)))

            self.event_bus.publish(
                NovaEvent.RESPONSE_GENERATED, text=response_text, provider=active_provider_name
            )

            if self._should_remember(resolved_text, analysis):
                self._write_memory(resolved_text, response_text, analysis)

            self._conversation_history.append({"role": "user", "content": resolved_text})
            self._conversation_history.append({"role": "assistant", "content": response_text})

            self.activity.last_conversation_topic = resolved_text[:200]
            self._deliver_response(response_text, turn_id)

        except Exception as exc:  # noqa: BLE001 - last line of defense for a turn
            logger.error(
                "[turn-%s] Unexpected error during conversation turn: %s",
                turn_id,
                exc,
                exc_info=True,
            )
        finally:
            self._processing_turn = False
            logger.info("[turn-%s] Turn finished.", turn_id)

    def _resolve_turn_input(self, request: TurnRequest, turn_id: str) -> str | None:
        """Resolve a :class:`TurnRequest` into the text this turn should process.

        Args:
            request: The triggering request.
            turn_id: This turn's correlation identifier, for logging.

        Returns:
            The input text to process, or ``None`` if the turn should
            be aborted.
        """
        raw_text = None
        if request.source == "voice":
            if request.text and request.text.strip():
                raw_text = request.text
            else:
                self.state_manager.set_state(VoiceState.LISTENING)
                self.event_bus.publish(NovaEvent.LISTENING_STARTED)

                if self.stt_manager is None or not self._voice_input_ready:
                    logger.warning(
                        "[turn-%s] Voice trigger received but speech-to-text is unavailable.",
                        turn_id,
                    )
                    self._voice_turn_queued = False
                    self.state_manager.set_state(VoiceState.LISTENING)
                    return None

                recognition = self.stt_manager.listen_once(interactive=True)
                if not recognition.success or not recognition.text:
                    logger.info(
                        "[turn-%s] Speech recognition did not produce usable text (status=%s).",
                        turn_id,
                        recognition.status.value,
                    )
                    self._in_conversation_flow = False
                    self._voice_turn_queued = False
                    self.state_manager.set_state(VoiceState.LISTENING)
                    return None
                raw_text = recognition.text
        else:
            raw_text = request.text or ""

        raw_text_clean = raw_text.lower().strip()

        # 1. Check if we are waiting for confirmation of a low-confidence command
        if getattr(self, "_pending_confirmation_command", None) is not None:
            pending_cmd = self._pending_confirmation_command
            pending_raw = getattr(self, "_pending_raw_input", "")

            # Reset states immediately so we don't loop
            self._pending_confirmation_command = None
            self._pending_raw_input = None

            is_positive = any(word in raw_text_clean for word in ["yes", "yeah", "correct", "haan", "sure", "ok", "yep", "confirm"])
            is_negative = any(word in raw_text_clean for word in ["no", "nah", "wrong", "cancel"])

            if is_positive:
                logger.info("[turn-%s] Boss confirmed command: '%s'", turn_id, pending_cmd)
                # Execute the confirmed command!
                mac_result = self.mac_control_manager.process_input(pending_cmd)
                if mac_result is not None:
                    voice_reply = self.mac_control_manager.get_voice_response(mac_result)
                    self._deliver_response(voice_reply, turn_id)
                else:
                    self._deliver_response(f"Executed command: {pending_cmd}", turn_id)
                return None

            elif is_negative:
                # Check if they corrected us (e.g. "No, I said Open Safari")
                correction_target = None
                for keyword in ["said ", "meant ", "say "]:
                    if keyword in raw_text_clean:
                        remainder = raw_text.split(keyword)[-1].strip()
                        # Capitalize words to normalize command
                        correction_target = " ".join(w.capitalize() for w in remainder.split())
                        break

                if correction_target:
                    # Save correction to self-learning JSON database
                    from voice.speech_to_text import save_speech_correction
                    save_speech_correction(pending_raw, correction_target)

                    self._deliver_response(f"Understood Boss. Learning correction. Running {correction_target}.", turn_id)
                    mac_result = self.mac_control_manager.process_input(correction_target)
                    if mac_result is not None:
                        voice_reply = self.mac_control_manager.get_voice_response(mac_result)
                        self._deliver_response(voice_reply, turn_id)
                    return None

                self._deliver_response("Okay Boss. Command cancelled.", turn_id)
                return None

            else:
                logger.info("[turn-%s] Unrecognized confirmation reply, treating as new command.", turn_id)

        # 2. Apply second-stage semantic command correction
        from voice.speech_to_text import correct_transcription_intent
        corrected_text, trans_conf, intent_conf = correct_transcription_intent(raw_text)
        logger.info(
            "[turn-%s] Raw transcript: '%s' -> Corrected: '%s' (trans_conf=%.1f%%, intent_conf=%.1f%%)",
            turn_id, raw_text, corrected_text, trans_conf, intent_conf
        )

        # 3. Intercept if confidence is less than 60% to ask the Boss
        if intent_conf < 60.0 or trans_conf < 60.0:
            self._pending_confirmation_command = corrected_text
            self._pending_raw_input = raw_text
            prompt_msg = f"Boss, I heard '{corrected_text}'. Is that correct?"
            self._deliver_response(prompt_msg, turn_id)
            return None

        # Expose parameters to DashboardStatsManager
        try:
            from ui.health_checker import DashboardStatsManager
            DashboardStatsManager.update("intent_confidence", f"{intent_conf:.1f}%")
        except Exception:
            pass

        return corrected_text

    def _peek_active_provider(self, task_type: TaskType) -> str | None:
        """Best-effort lookup of which provider would currently serve a task type.

        This is purely descriptive context for the prompt (see
        ``PromptBuildContext.current_provider``); it never fails the
        turn if no provider is currently available.

        Args:
            task_type: The task type to check.

        Returns:
            The provider's name, or ``None`` if none is available.
        """
        if self.provider_manager is None:
            return None
        try:
            return self.provider_manager.choose_provider(task_type=task_type, mode="auto").provider_name
        except AllProvidersFailedError:
            return None

    def _generate_response(
        self,
        user_text: str,
        context: PromptBuildContext,
        profile_name: str,
        task_type: TaskType,
        turn_id: str,
    ) -> str | None:
        """Build a prompt and call the provider layer to generate a response.

        Args:
            user_text: The user's (resolved) input text.
            context: The prompt context for this turn.
            profile_name: The personality profile to build with.
            task_type: The task type used for provider routing.
            turn_id: This turn's correlation identifier, for logging.

        Returns:
            The generated response text, or ``None`` if generation
            failed and a graceful apology was already delivered.
        """
        assert self.system_prompt_manager is not None
        assert self.provider_manager is not None

        try:
            prompt_text = self.system_prompt_manager.build_prompt(
                profile=profile_name, context=context
            )
        except ProfileNotFoundError:
            prompt_text = self.system_prompt_manager.build_prompt(
                profile=ProfileName.DEFAULT.value, context=context
            )

        # Append recent conversation history context to preserve context memory
        if self._conversation_history:
            history_lines = []
            for msg in self._conversation_history[-10:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                history_lines.append(f"{role}: {msg['content']}")
            prompt_text += "\n\n## Recent Conversation History\n" + "\n".join(history_lines) + "\n"

        override_provider = self._manual_provider_override
        self._manual_provider_override = None

        try:
            if override_provider:
                return self.provider_manager.generate_response(
                    prompt=user_text,
                    system_prompt=prompt_text,
                    task_type=task_type,
                    mode="manual",
                    provider_name=override_provider,
                )
            return self.provider_manager.generate_response(
                prompt=user_text,
                system_prompt=prompt_text,
                task_type=task_type,
                mode="auto",
            )
        except AllProvidersFailedError as exc:
            logger.error("[turn-%s] All providers failed: %s", turn_id, exc)
            self._deliver_response(
                "I'm having trouble reaching my thinking engines right now.", turn_id
            )
            return None

    def _deliver_response(self, text: str, turn_id: str) -> None:
        """Deliver a response through every available output channel.

        Always prints to the console (the text-first guarantee); also
        speaks the response asynchronously if text-to-speech is
        available.

        Args:
            text: The text to deliver.
            turn_id: This turn's correlation identifier, for logging.
        """
        if getattr(self, "_current_turn_source", "text") == "voice":
            print("====================================================")
            print("🤖 NOVA SPEAKING")
            print(text)
            print("====================================================")
        else:
            print(f"NOVA: {text}")

        if self.tts_manager is not None and self._voice_output_ready:
            self.event_bus.publish(NovaEvent.SPEAKING_STARTED, text=text)
            self._current_spoken_text = text.lower()

            def _on_speech_complete(result: Any) -> None:
                self._assistant_speaking = False
                self._current_spoken_text = ""
                self._stop_interruption_monitor()

                # Enforce a 500 ms settling pause to let room echo dissipate
                time.sleep(0.50)

                if self.stt_manager is not None:
                    self.stt_manager.clear_microphone_queue()
                self.event_bus.publish(NovaEvent.SPEAKING_FINISHED, success=result.success)

                # Chain next continuous conversation turn immediately!
                if self._voice_input_ready and self._in_conversation_flow and not self._shutdown_requested.is_set():
                    if not self._voice_turn_queued:
                        self._voice_turn_queued = True
                        logger.info("[turn-%s] Speech complete. Continuing voice conversation flow.", turn_id)
                        self._processing_turn = True
                        self._turn_queue.put(TurnRequest(source="voice"))

            self._assistant_speaking = True
            self._start_interruption_monitor()
            self.tts_manager.speak_async(text, on_complete=_on_speech_complete)
        else:
            logger.debug("[turn-%s] Text-to-speech unavailable; delivered as text only.", turn_id)
            if self._voice_input_ready and self._in_conversation_flow and not self._shutdown_requested.is_set():
                if not self._voice_turn_queued:
                    self._voice_turn_queued = True
                    self._processing_turn = True
                    self._turn_queue.put(TurnRequest(source="voice"))

    def _start_interruption_monitor(self) -> None:
        """Start a background thread to listen for interruption words during TTS playback."""
        self._stop_interruption_monitor()
        self._interruption_event.clear()
        self._interruption_thread = threading.Thread(
            target=self._interruption_monitor_loop,
            daemon=True,
            name="nova-interruption-monitor"
        )
        self._interruption_thread.start()

    def _stop_interruption_monitor(self) -> None:
        """Stop the background interruption monitor thread."""
        self._interruption_event.set()
        if self._interruption_thread:
            self._interruption_thread.join(timeout=0.1)
            self._interruption_thread = None

    def _interruption_monitor_loop(self) -> None:
        """Monitor microphone stream using a 2-stage interruption pipeline."""
        if self.stt_manager is None or not self.stt_manager._initialized:
            return

        recognizer = self.stt_manager._recognizer
        if not hasattr(recognizer, "_mic_stream") or recognizer._mic_stream is None:
            return

        mic = recognizer._mic_stream
        mic.start("interruption_monitor")
        mic.clear_queue()

        # Audio VAD for Stage 1
        from voice.speech_to_text import AudioVAD
        vad = AudioVAD(sample_rate=16000, frame_duration_ms=30)

        try:
            while not self._interruption_event.is_set() and self._assistant_speaking:
                chunk = mic.read_chunk(timeout=0.05)
                if not chunk:
                    continue

                # Check VAD (Stage 1)
                frame_int16 = np.frombuffer(chunk, dtype=np.int16)
                frame_float32 = frame_int16.astype(np.float32) / 32768.0
                is_speech = vad.process_frame(frame_float32)

                if is_speech:
                    # Speech detected (Stage 1 trigger) -> Record 500 ms (Stage 2)
                    speech_buffer = bytearray(chunk)

                    # 16 chunks of 30ms = 480ms (total ~510ms with trigger chunk)
                    for _ in range(16):
                        c = mic.read_chunk(timeout=0.05)
                        if c:
                            speech_buffer.extend(c)

                    buf_int16 = np.frombuffer(bytes(speech_buffer), dtype=np.int16)
                    buf_float32 = buf_int16.astype(np.float32) / 32768.0

                    try:
                        # Quick high-quality transcription pass
                        segments, info = recognizer._model.transcribe(
                            buf_float32,
                            beam_size=5,
                            best_of=5,
                            temperature=0.0,
                            vad_filter=True,
                            condition_on_previous_text=False
                        )

                        segments = list(segments)
                        if not segments:
                            continue

                        # Validate segments
                        valid_text_list = []

                        for seg in segments:
                            # 1. Metadata thresholds to reject background noise/garbage
                            if seg.no_speech_prob > 0.35:
                                continue
                            if seg.avg_logprob < -0.9:
                                continue
                            if seg.compression_ratio > 2.4:
                                continue

                            # 2. Text validation
                            seg_text = seg.text.strip()
                            if not seg_text:
                                continue

                            # Check for alphanumeric words
                            words = seg_text.lower().split()
                            clean_words = [re.sub(r'[^\w\s]', '', w) for w in words]
                            clean_words = [w for w in clean_words if w]
                            if not clean_words:
                                continue

                            # 3. Repetition check
                            unique_words = set(clean_words)
                            if len(clean_words) >= 4 and len(unique_words) / len(clean_words) < 0.45:
                                continue

                            valid_text_list.append(seg_text)

                        if not valid_text_list:
                            continue

                        full_text = " ".join(valid_text_list).strip()
                        if not full_text:
                            continue

                        # 4. Self-voice immunity filter: ignore echoes of NOVA's own speaking output
                        is_self_voice = False
                        if self._current_spoken_text:
                            clean_transcribed = re.sub(r'[^\w\s]', '', full_text.lower()).strip()
                            clean_spoken = re.sub(r'[^\w\s]', '', self._current_spoken_text.lower()).strip()
                            if clean_transcribed and clean_transcribed in clean_spoken:
                                is_self_voice = True

                        if not is_self_voice:
                            logger.info("Speech playback interrupted by Boss: '%s'", full_text)
                            sys.stdout.write(f"\n\033[91m🛑 Interrupted by Boss: '{full_text}'\033[0m\n")
                            sys.stdout.flush()

                            # Stop active speech output
                            if self.tts_manager:
                                self.tts_manager.stop()
                            self._assistant_speaking = False

                            # Trigger continuous voice conversation flow immediately
                            self._in_conversation_flow = True
                            break
                    except Exception as exc:
                        logger.debug("Interruption transcription error: %s", exc)

                    # Reset VAD and clear queue to ignore processing lag audio
                    vad = AudioVAD(sample_rate=16000, frame_duration_ms=30)
                    mic.clear_queue()
        finally:
            mic.stop("interruption_monitor")

    # -------------------------------------------------------------------
    # Memory integration
    # -------------------------------------------------------------------

    def _build_memory_summary(self, query_text: str) -> str | None:
        """Retrieve and merge relevant durable memory for a query.

        Args:
            query_text: The text to search memory and vector storage
                with.

        Returns:
            A short, merged summary string, or ``None`` if nothing
            relevant was found or memory could not be read.
        """
        parts: list[str] = []

        if self.memory_manager is not None:
            try:
                for entry in self.memory_manager.search_memory(query=query_text)[:5]:
                    parts.append(f"{entry.category.value}: {entry.key} = {entry.value}")
            except NovaMemoryError as exc:
                logger.warning("Memory search failed: %s", exc)

        if self.vector_store is not None:
            try:
                for result in self.vector_store.search(query_text, top_k=3):
                    parts.append(result.document.text)
            except Exception as exc:  # noqa: BLE001 - retrieval must never fail a turn
                logger.warning("Vector store search failed: %s", exc)

        return "; ".join(parts) if parts else None

    def _should_remember(self, user_text: str, analysis: ConversationAnalysis) -> bool:
        """Decide whether a turn is durable enough to write to memory.

        This is a deliberately simple heuristic, owned by this module
        per the architecture document (Memory should stay a reliable
        store, not a decision-maker): turns in project/task-relevant
        conversation modes, or turns where the detected mode was
        identified with high confidence, are considered worth keeping.

        Args:
            user_text: The user's (resolved) input text.
            analysis: This turn's emotion/mode analysis.

        Returns:
            ``True`` if the turn should be written to durable memory.
        """
        durable_modes = {
            ConversationMode.CODING,
            ConversationMode.DEBUGGING,
            ConversationMode.DSA,
            ConversationMode.STUDY,
            ConversationMode.INTERVIEW,
            ConversationMode.PLANNING,
        }
        if analysis.detected_mode in durable_modes:
            return True
        return analysis.mode_confidence >= 0.66 and len(user_text) > 40

    def _write_memory(
        self, user_text: str, response_text: str, analysis: ConversationAnalysis
    ) -> None:
        """Persist a conversational turn to durable memory.

        Args:
            user_text: The user's (resolved) input text.
            response_text: NOVA's generated response.
            analysis: This turn's emotion/mode analysis.
        """
        category = self._map_mode_to_memory_category(analysis.detected_mode)
        turn_summary = f"User: {user_text}\nNOVA: {response_text}"

        if self.memory_manager is not None:
            try:
                self.memory_manager.add_memory(
                    category=category,
                    key=f"turn-{uuid.uuid4().hex[:8]}",
                    value=turn_summary,
                    importance=3,
                    tags=(analysis.detected_mode.value,),
                )
            except NovaMemoryError as exc:
                logger.warning("Failed to write memory entry: %s", exc)

        if self.vector_store is not None:
            try:
                self.vector_store.add_document(
                    text=turn_summary,
                    category=category.value,
                    tags=(analysis.detected_mode.value,),
                )
            except Exception as exc:  # noqa: BLE001 - indexing must never fail a turn
                logger.warning("Failed to index memory in the vector store: %s", exc)

    # -------------------------------------------------------------------
    # Mode-mapping glue (owned by main.py per the architecture document)
    # -------------------------------------------------------------------

    @staticmethod
    def _map_mode_to_task_type(mode: ConversationMode) -> TaskType:
        """Map a detected conversation mode to a provider routing task type.

        Args:
            mode: The detected conversation mode.

        Returns:
            The corresponding :class:`TaskType`.
        """
        mapping = {
            ConversationMode.CODING: TaskType.CODING,
            ConversationMode.DEBUGGING: TaskType.CODING,
            ConversationMode.DSA: TaskType.CODING,
            ConversationMode.STUDY: TaskType.REASONING,
            ConversationMode.INTERVIEW: TaskType.REASONING,
            ConversationMode.PLANNING: TaskType.REASONING,
            ConversationMode.MOTIVATION: TaskType.FAST,
            ConversationMode.CASUAL: TaskType.FAST,
            ConversationMode.FRIEND: TaskType.GENERAL,
            ConversationMode.GENERAL: TaskType.GENERAL,
        }
        return mapping.get(mode, TaskType.GENERAL)

    @staticmethod
    def _map_mode_to_profile(mode: ConversationMode) -> str:
        """Map a detected conversation mode to a personality profile name.

        Args:
            mode: The detected conversation mode.

        Returns:
            The corresponding profile name. ``ConversationMode.PLANNING``
            has no dedicated profile in ``SystemPromptManager`` today,
            so it falls back to ``ProfileName.DEFAULT`` rather than
            inventing a new profile here.
        """
        mapping = {
            ConversationMode.CODING: ProfileName.CODING.value,
            ConversationMode.DEBUGGING: ProfileName.DEBUGGING.value,
            ConversationMode.STUDY: ProfileName.STUDY.value,
            ConversationMode.DSA: ProfileName.DSA.value,
            ConversationMode.INTERVIEW: ProfileName.INTERVIEW.value,
            ConversationMode.MOTIVATION: ProfileName.MOTIVATIONAL.value,
            ConversationMode.CASUAL: ProfileName.CASUAL.value,
            ConversationMode.FRIEND: ProfileName.FRIEND.value,
        }
        return mapping.get(mode, ProfileName.DEFAULT.value)

    @staticmethod
    def _map_mode_to_memory_category(mode: ConversationMode) -> MemoryCategory:
        """Map a detected conversation mode to a memory category.

        Args:
            mode: The detected conversation mode.

        Returns:
            The corresponding :class:`MemoryCategory`.
        """
        mapping = {
            ConversationMode.CODING: MemoryCategory.CODING,
            ConversationMode.DEBUGGING: MemoryCategory.CODING,
            ConversationMode.DSA: MemoryCategory.CODING,
            ConversationMode.STUDY: MemoryCategory.EDUCATION,
            ConversationMode.INTERVIEW: MemoryCategory.EDUCATION,
            ConversationMode.PLANNING: MemoryCategory.TASKS,
            ConversationMode.MOTIVATION: MemoryCategory.GOALS,
            ConversationMode.FRIEND: MemoryCategory.CONVERSATIONS,
            ConversationMode.CASUAL: MemoryCategory.CONVERSATIONS,
            ConversationMode.GENERAL: MemoryCategory.CONVERSATIONS,
        }
        return mapping.get(mode, MemoryCategory.CONVERSATIONS)

    # -------------------------------------------------------------------
    # Companion Shutdown Flow
    # -------------------------------------------------------------------

    def _companion_shutdown_flow(self) -> None:
        """Generate and deliver NOVA's farewell, then write the session breadcrumb.

        Implemented as one more synthetic conversation turn, exactly
        mirroring the Companion Startup Flow (§5/§11 of the
        architecture document).
        """
        self.event_bus.publish(NovaEvent.APPLICATION_SHUTDOWN)

        session_length = datetime.now(UTC) - self.activity.session_start_time
        farewell = "See you soon Boss."

        self.event_bus.publish(NovaEvent.RESPONSE_GENERATED, text=farewell, provider=None)
        self._deliver_response(farewell, turn_id="shutdown")

        summary = (
            f"project={self.activity.current_project or 'none'}; "
            f"topic={self.activity.last_conversation_topic or 'none'}; "
            f"session_length={session_length}"
        )
        self._write_breadcrumb(summary)

    def _execute_local_shutdown(self) -> None:
        """Locally handle shutdown command, print structured progress cards, and exit cleanly."""
        self._is_already_shutting_down = True
        farewell = "See you soon Boss."

        print("\n----------------------------------------")
        print("👤 YOU")
        print(getattr(self, "_last_turn_input", "shutdown"))
        print("\n🟢 Shutdown command detected.")
        print("\n💾 Saving memory...")
        session_length = datetime.now(UTC) - self.activity.session_start_time
        summary = (
            f"project={self.activity.current_project or 'none'}; "
            f"topic={self.activity.last_conversation_topic or 'none'}; "
            f"session_length={session_length}"
        )
        self._write_breadcrumb(summary)
        if self.memory_manager is not None:
            try:
                self.memory_manager.shutdown()
            except Exception as exc:
                logger.debug("Error saving memory manager during local shutdown: %s", exc)

        print("\n🎤 Stopping microphone...")
        if self.stt_manager is not None and self._voice_input_ready:
            try:
                self.stt_manager.shutdown()
            except Exception as exc:
                logger.debug("Error shutting down STT: %s", exc)

        print("\n🔊 Stopping speech...")
        if self.tts_manager is not None and self._voice_output_ready:
            print("\nNOVA:")
            print(farewell)
            print("----------------------------------------\n")
            try:
                self.tts_manager.speak(farewell)
            except Exception as exc:
                logger.debug("Error speaking farewell: %s", exc)
            try:
                self.tts_manager.shutdown()
            except Exception as exc:
                logger.debug("Error shutting down TTS: %s", exc)
        else:
            print("\nNOVA:")
            print(farewell)
            print("----------------------------------------\n")

        print("\n🧠 Closing AI services...")
        if self.provider_manager is not None:
            try:
                self.provider_manager.shutdown()
            except Exception as exc:
                logger.debug("Error shutting down provider manager: %s", exc)

        try:
            lifecycle.shutdown()
        except Exception as exc:
            logger.debug("Error shutting down lifecycle: %s", exc)

        print("\n🟢 Session closed.")
        sys.exit(0)

    def _shutdown(self) -> None:
        """Tear down every subsystem in reverse initialization order.

        Every step is individually contained: a failure at any point
        is logged and never prevents the remaining steps from running.
        """
        if getattr(self, "_is_already_shutting_down", False):
            return
        self._is_already_shutting_down = True
        logger.info("NOVA is shutting down.")

        try:
            self._companion_shutdown_flow()
        except Exception as exc:  # noqa: BLE001 - shutdown must proceed regardless
            logger.error("Companion shutdown flow failed: %s", exc, exc_info=True)

        if self.tts_manager is not None:
            try:
                self.tts_manager.stop(clear_queue=True)
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to stop text-to-speech: %s", exc, exc_info=True)

        try:
            lifecycle.shutdown()
        except Exception as exc:  # noqa: BLE001
            logger.error("Lifecycle shutdown failed: %s", exc, exc_info=True)

        for name, manager, ready in (
            ("tts_manager", self.tts_manager, self._voice_output_ready),
            ("stt_manager", self.stt_manager, self._voice_input_ready),
        ):
            if manager is None or not ready:
                continue
            try:
                manager.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to shut down %s: %s", name, exc, exc_info=True)

        if self.provider_manager is not None:
            try:
                self.provider_manager.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.error("Failed to shut down the provider manager: %s", exc, exc_info=True)

        if self.system_prompt_manager is not None:
            try:
                self.system_prompt_manager.shutdown()
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Failed to shut down the system prompt manager: %s", exc, exc_info=True
                )

        logger.info("NOVA has shut down.")


def main() -> int:
    """Construct and run a NOVA application instance.

    Returns:
        The process exit code.
    """
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        try:
            from ui.doctor import Doctor
            doc = Doctor()
            return doc.run()
        except Exception as exc:
            print(f"Failed to execute doctor diagnostics: {exc}")
            return 1

    application = NovaApplication()
    return application.run()


if __name__ == "__main__":
    sys.exit(main())
