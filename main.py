"""NOVA's application entry point and central orchestrator.

Coordinates lifecycle, service registry, event bus, memory, AI providers,
personality engine, macOS hardware automation, and Voice V2.
"""

from __future__ import annotations

import queue
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pathlib import Path

from config.settings import settings
from core.computer_agent import ComputerAgent, computer_agent
from core.environment import ContextResolver, EnvironmentObserver, environment_observer, log_environment_debug
from core.event_bus import EventBus, EventHandler, NovaEvent
from core.exceptions import MemorySystemError as NovaMemoryError
from core.lifecycle import lifecycle
from core.logger import get_logger, setup_logging
from core.screen_recording import ScreenRecordingManager, screen_recording_manager
from core.screenshot import ScreenshotService, screenshot_service
from core.task_agent import TaskContext, TaskExecutor, TaskPlanner, task_executor
from browser import BrowserManager
from desktop.manager import DesktopActionManager
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent
from intent.router import RoutingDomain, get_routing_domain
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
from ui.health_checker import DashboardStatsManager
from voice import QualityDecision, TranscriptionResult, VoiceManager, VoiceState
from voice.commands import CommandRecognizer, VoiceCommandRouter

logger = get_logger(__name__)

_BREADCRUMB_KEY = "last_session_summary"
_GREETING_PROFILE_NAME = "greeting"
_FAREWELL_PROFILE_NAME = "farewell"
_TURN_QUEUE_POLL_SECONDS = 0.5

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


@dataclass
class ActivityState:
    """Ephemeral runtime state tracked only in-process."""

    current_project: str | None = None
    current_task: str | None = None
    session_start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_conversation_topic: str | None = None


@dataclass(frozen=True)
class TurnRequest:
    """A single unit of interaction for NOVA's conversation pipeline."""

    source: str  # "voice" or "text"
    text: str = ""
    raw_transcript: str = ""
    normalized_transcript: str = ""
    confidence: float = 1.0
    transcription: Any = None
    audio_event: str = "none"
    is_isolated_audio_event: bool = False


class NovaApplication:
    """NOVA's primary orchestrator: owns startup, the turn queue, event loop, and teardown."""

    def __init__(self) -> None:
        self.event_bus: EventBus = EventBus()
        self.activity: ActivityState = ActivityState()

        # Core subsystems
        self.memory_manager: MemoryManager | None = None
        self.vector_store: VectorStore | None = None
        self.provider_manager: ProviderManager | None = None
        self.system_prompt_manager: SystemPromptManager | None = None
        self.emotion_engine: EmotionEngine | None = None
        # Desktop, Browser & Autonomous Task Subsystems
        self.desktop_manager: DesktopActionManager = DesktopActionManager()
        self.browser_manager: BrowserManager = BrowserManager()
        self.mac_control_manager: MacControlManager | None = None
        self.computer_agent: ComputerAgent = computer_agent
        self.task_planner: TaskPlanner = TaskPlanner()
        self.task_executor: TaskExecutor = task_executor
        self.active_task_context: TaskContext = TaskContext(task_id="global_turn_context")
        self.environment_observer: EnvironmentObserver = environment_observer
        self.screen_recording_manager: ScreenRecordingManager = screen_recording_manager
        self.intent_engine: NaturalLanguageIntentEngine = NaturalLanguageIntentEngine()

        # Voice V2 Subsystem
        self.voice_manager: VoiceManager = VoiceManager()
        self.voice_available: bool = False

        # Turn Queue & Synchronization
        self._turn_queue: queue.Queue[TurnRequest] = queue.Queue()
        self._shutdown_requested = threading.Event()
        self._is_already_shutting_down = False
        self._console_thread: threading.Thread | None = None
        self._manual_provider_override: str | None = None

        # Local Command Router
        self.command_recognizer = CommandRecognizer()
        self.command_router = VoiceCommandRouter(self.command_recognizer)
        self.command_router.register_handler("shutdown", self._execute_local_shutdown)
        self.command_router.register_handler("cancel", self._execute_local_cancel)

        # Context History
        self._conversation_history: list[dict[str, str]] = []
        self._last_turn_input: str = ""

    def run(self) -> int:
        """Run NOVA end to end: startup, subsystem initialization, event loop, shutdown."""
        try:
            setup_logging()
            lifecycle.start()
            lifecycle.register_service("event_bus", self.event_bus)
        except Exception as exc:
            logger.critical("NOVA failed initial bootstrap: %s", exc, exc_info=True)
            return 1

        logger.info("NOVA is starting.")

        # 1. Parallel initialization of independent subsystems
        init_threads = []
        init_errors: list[Exception] = []

        def _run_init(func: Any, name: str) -> None:
            try:
                func()
            except Exception as err:
                logger.critical("Subsystem '%s' failed to initialize: %s", name, err, exc_info=True)
                init_errors.append(err)

        for init_fn, name in [
            (self._initialize_memory, "memory"),
            (self._initialize_providers, "providers"),
            (self._initialize_personality, "personality"),
            (self._initialize_mac_control, "mac_control"),
            (self._initialize_desktop, "desktop"),
            (self._initialize_browser, "browser"),
            (self._initialize_computer_agent, "computer_agent"),
        ]:
            t = threading.Thread(target=_run_init, args=(init_fn, name), daemon=True, name=f"nova-init-{name}")
            t.start()
            init_threads.append(t)

        for t in init_threads:
            t.join()

        if init_errors:
            self._shutdown()
            return 1

        # 2. Initialize Voice V2 Subsystem
        self._initialize_voice()

        # 3. Register signal handlers
        self._register_signal_handlers()

        # 4. Render Terminal Operations Dashboard
        try:
            from ui.terminal_dashboard import TerminalDashboard

            dashboard = TerminalDashboard()
            dashboard.render()
        except Exception as exc:
            logger.error("Failed to render terminal dashboard: %s", exc, exc_info=True)

        # 5. Companion Startup Flow & Greeting
        self._companion_startup_flow()

        self.event_bus.publish(
            NovaEvent.APPLICATION_STARTED,
            voice_available=self.voice_available,
            last_active_project=self.activity.current_project,
        )

        # 6. Start input listeners (Console + Voice V2)
        self._start_background_services()

        # 7. Run main event loop
        exit_code = 0
        try:
            self._run_event_loop()
        except Exception as exc:
            logger.critical("Fatal error in main event loop: %s", exc, exc_info=True)
            exit_code = 1
        finally:
            self._shutdown()

        return exit_code

    # -------------------------------------------------------------------
    # Subsystem Initializations
    # -------------------------------------------------------------------

    def _initialize_memory(self) -> None:
        """Construct and register durable memory and semantic vector storage."""
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
            logger.warning("Failed to populate VectorStore with existing memories: %s", exc)

        logger.info("Memory subsystem initialized.")

    def _initialize_providers(self) -> None:
        """Construct and initialize AI providers (Gemini, Groq, OpenRouter, Cerebras)."""
        self.provider_manager = ProviderManager()
        self.provider_manager.initialize()
        lifecycle.register_service("provider_manager", self.provider_manager)
        logger.info(
            "Providers subsystem initialized (available: %s).",
            ", ".join(self.provider_manager.get_available_providers()) or "none",
        )

    def _initialize_personality(self) -> None:
        """Construct and register SystemPromptManager and EmotionEngine."""
        self.system_prompt_manager = SystemPromptManager()
        self.system_prompt_manager.initialize()
        self._register_companion_profiles()
        lifecycle.register_service("system_prompt_manager", self.system_prompt_manager)

        self.emotion_engine = EmotionEngine()
        lifecycle.register_service("emotion_engine", self.emotion_engine)

        logger.info("Personality subsystem initialized.")

    def _initialize_mac_control(self) -> None:
        """Construct and register macOS hardware/application control orchestrator."""
        self.mac_control_manager = MacControlManager()
        lifecycle.register_service("mac_control_manager", self.mac_control_manager)
        logger.info("macOS Control subsystem initialized.")

    def _initialize_desktop(self) -> None:
        """Construct and initialize desktop actions subsystem."""
        try:
            self.desktop_manager.initialize()
            lifecycle.register_service("desktop_manager", self.desktop_manager)
            logger.info("Desktop Actions subsystem initialized.")
        except Exception as exc:
            logger.warning("Desktop Actions initialization note: %s", exc)

    def _initialize_browser(self) -> None:
        """Construct and initialize browser automation subsystem."""
        try:
            self.browser_manager.initialize()
            lifecycle.register_service("browser_manager", self.browser_manager)
            logger.info("Browser Actions subsystem initialized.")
        except Exception as exc:
            logger.warning("Browser Actions initialization note: %s", exc)

    def _initialize_computer_agent(self) -> None:
        """Initialize NOVA Eyes + Computer Interaction Agent."""
        try:
            self.computer_agent.initialize()
            logger.info("ComputerAgent (NOVA Eyes) initialized.")
        except Exception as exc:
            logger.warning("ComputerAgent initialization note: %s", exc)

    def _initialize_voice(self) -> None:
        """Initialize Voice V2 subsystem."""
        try:
            self.voice_manager.initialize()
            self.voice_available = self.voice_manager.health_check()
            lifecycle.register_service("voice_manager", self.voice_manager)
            logger.info("Voice V2 initialized (available=%s).", self.voice_available)
        except Exception as exc:
            logger.warning("Voice V2 initialization failed gracefully: %s", exc)
            self.voice_available = False

    def _register_companion_profiles(self) -> None:
        """Register greeting and farewell profiles with SystemPromptManager."""
        assert self.system_prompt_manager is not None

        greeting_profile = PromptProfile(
            name=_GREETING_PROFILE_NAME,
            description="Generates NOVA's startup greeting.",
            section_names=_COMPANION_PROFILE_SECTIONS,
            focus_instruction=(
                "This is the start of a session. Greet the user naturally, "
                "referencing the time of day and last active topic/project if available."
            ),
        )
        farewell_profile = PromptProfile(
            name=_FAREWELL_PROFILE_NAME,
            description="Generates NOVA's end-of-session farewell.",
            section_names=_COMPANION_PROFILE_SECTIONS,
            focus_instruction="Say a brief, natural, warm farewell to the user.",
        )

        for profile in (greeting_profile, farewell_profile):
            try:
                self.system_prompt_manager.register_profile(profile)
            except DuplicateProfileError:
                pass

    def _register_signal_handlers(self) -> None:
        """Register SIGINT/SIGTERM handlers."""

        def _handle_signal(signum: int, _frame: Any) -> None:
            logger.info("Signal %s received; initiating shutdown.", signum)
            self._shutdown_requested.set()

        for sig_name in ("SIGINT", "SIGTERM"):
            sig = getattr(signal, sig_name, None)
            if sig is not None:
                try:
                    signal.signal(sig, _handle_signal)
                except Exception:
                    pass

    # -------------------------------------------------------------------
    # Startup and Shutdown Flows
    # -------------------------------------------------------------------

    def _companion_startup_flow(self) -> None:
        """Generate and deliver NOVA's context-aware companion startup greeting."""
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
        except Exception as exc:
            logger.warning("Could not generate dynamic startup greeting: %s. Using default.", exc)
            greeting = "NOVA is online. How can I help you today, Boss?"

        self.event_bus.publish(NovaEvent.RESPONSE_GENERATED, text=greeting, provider=None)
        self._deliver_response(greeting, turn_id="startup")

    def _get_last_active_project(self) -> str | None:
        if self.memory_manager is None:
            return None
        try:
            entries = self.memory_manager.get_by_category(MemoryCategory.PROJECTS)
            if entries:
                latest = max(entries, key=lambda e: e.updated_at)
                return str(latest.value) if latest.value else latest.key
        except Exception:
            pass
        return None

    def _read_breadcrumb(self) -> str | None:
        if self.memory_manager is None:
            return None
        try:
            results = self.memory_manager.search_memory(query=_BREADCRUMB_KEY, exact_key=True)
            if results:
                return str(results[0].value)
        except Exception:
            pass
        return None

    def _write_breadcrumb(self, summary: str) -> None:
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
        except Exception as exc:
            logger.warning("Could not write session breadcrumb: %s", exc)

    # -------------------------------------------------------------------
    # Event Loop & Input Capture
    # -------------------------------------------------------------------

    def _start_background_services(self) -> None:
        """Start console reader thread and continuous voice listener."""
        # 1. Console typed input loop
        self._console_thread = threading.Thread(
            target=self._console_input_loop,
            name="nova-console-input",
            daemon=True,
        )
        self._console_thread.start()

        # 2. Voice V2 continuous listening
        if self.voice_available:
            def _on_voice_turn(transcription: TranscriptionResult) -> None:
                has_content = bool(transcription.text) or getattr(transcription, "is_isolated_audio_event", False)
                if has_content and not self._shutdown_requested.is_set():
                    self._last_voice_transcription = transcription
                    self._turn_queue.put(
                        TurnRequest(
                            source="voice",
                            text=transcription.text,
                            raw_transcript=getattr(transcription, "raw_text", "") or transcription.text,
                            normalized_transcript=getattr(transcription, "normalized_text", "") or transcription.text,
                            confidence=transcription.confidence,
                            transcription=transcription,
                            audio_event=getattr(transcription, "audio_event", "none"),
                            is_isolated_audio_event=getattr(transcription, "is_isolated_audio_event", False),
                        )
                    )

            self.voice_manager.start_listening(_on_voice_turn)
            logger.info("Voice V2 continuous listening engaged.")

    def _console_input_loop(self) -> None:
        """Read console lines and enqueue them as turn requests."""
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

            # Interactive Log Console Slash Commands
            if stripped.startswith("/"):
                cmd_parts = stripped.split(maxsplit=1)
                cmd_name = cmd_parts[0].lower()
                cmd_arg = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""

                from ui.terminal_dashboard import TerminalDashboard
                dashboard = TerminalDashboard.get_instance()

                if cmd_name in ("/clear", "/cls"):
                    if dashboard:
                        dashboard.clear_feed()
                    else:
                        DashboardStatsManager.clear_logs()
                    continue
                elif cmd_name in ("/filter", "/mode"):
                    if dashboard:
                        if cmd_arg:
                            dashboard.set_filter_mode(cmd_arg)
                        else:
                            dashboard.cycle_filter()
                    continue
                elif cmd_name == "/search":
                    if dashboard:
                        dashboard.set_search_query(cmd_arg)
                    continue
                elif cmd_name in ("/jump", "/latest"):
                    if dashboard:
                        dashboard.jump_to_latest()
                    continue
                elif cmd_name == "/top":
                    if dashboard:
                        dashboard.jump_to_top()
                    continue
                elif cmd_name in ("/scroll", "/up", "/down"):
                    if dashboard:
                        lines = 5
                        if cmd_name == "/up" or "up" in cmd_arg:
                            nums = [int(s) for s in cmd_arg.split() if s.isdigit()]
                            lines = nums[0] if nums else 5
                            dashboard.scroll_up(lines)
                        else:
                            nums = [int(s) for s in cmd_arg.split() if s.isdigit()]
                            lines = nums[0] if nums else 5
                            dashboard.scroll_down(lines)
                    continue
                elif cmd_name in ("/max", "/expand"):
                    if dashboard:
                        dashboard.toggle_maximize()
                    continue
                elif cmd_name in ("/copy", "/copylogs", "/copyfeed"):
                    if dashboard:
                        dashboard.copy_to_clipboard()
                    else:
                        DashboardStatsManager.copy_activity_to_clipboard()
                    continue
                elif cmd_name == "/help":
                    print("\n📋 NOVA Operations Control Center & Activity Feed Commands:")
                    print("  /clear, /cls          - Clear user activity feed display")
                    print("  /filter [CATEGORY]    - Filter by ACTIVITY, YOU, UNDERSTOOD, ACTION, NOVA, RESULT, DEBUG, ALL")
                    print("  /mode [activity|debug]- Switch between User Activity Feed and Raw Debug Logs")
                    print("  /search <term>        - Filter activity feed by keyword")
                    print("  /jump, /latest        - Jump to latest activity and resume auto-scroll")
                    print("  /top                  - Jump to top of activity history")
                    print("  /scroll up [N], /up   - Scroll up N lines (pauses auto-scroll)")
                    print("  /scroll down [N], /down - Scroll down N lines")
                    print("  /max, /expand         - Toggle full-screen Activity Feed")
                    print("  /copy, /copylogs      - Copy activity feed text to system clipboard")
                    print("  /provider <name>      - Set active AI provider override")
                    print("  exit, quit            - Gracefully shut down NOVA\n")
                    continue

            from voice.audio_events import AudioEventDetector
            audio_res = AudioEventDetector.analyze(stripped)
            clean_text = audio_res.clean_text if audio_res.clean_text else stripped
            self._turn_queue.put(
                TurnRequest(
                    source="text",
                    text=clean_text,
                    raw_transcript=stripped,
                    audio_event=audio_res.event_type.value,
                    is_isolated_audio_event=audio_res.is_isolated_event,
                )
            )

    def _run_event_loop(self) -> None:
        """Consume and process turns from the turn queue."""
        while not self._shutdown_requested.is_set():
            try:
                request = self._turn_queue.get(timeout=_TURN_QUEUE_POLL_SECONDS)
            except queue.Empty:
                continue
            self._process_turn(request)

    # -------------------------------------------------------------------
    # Turn Execution Pipeline
    # -------------------------------------------------------------------

    def _process_turn(self, request: TurnRequest) -> None:
        """Run one complete interaction turn."""
        turn_id = uuid.uuid4().hex[:8]
        user_text = request.text.strip()

        if request.is_isolated_audio_event:
            self._last_turn_input = f"[{request.audio_event}]"
            self._current_turn_source = request.source
            self._current_turn_id = turn_id
            DashboardStatsManager.start_interaction(
                f"[{request.audio_event}]", source=request.source, interaction_id=f"turn_{turn_id}"
            )
            DashboardStatsManager.record_heard(f"[{request.audio_event}]")
            DashboardStatsManager.record_understood("Acoustic Audio Event")
            if request.audio_event in ("cough", "throat_clear"):
                care_reply = "Boss, you okay? That sounded like a pretty bad cough."
            elif request.audio_event == "sneeze":
                care_reply = "Bless you! You okay?"
            elif request.audio_event == "laughter":
                care_reply = "Haha, what's making you laugh?"
            elif request.audio_event == "sigh":
                care_reply = "Heavy sigh... everything alright?"
            else:
                care_reply = "You okay?"
            self._deliver_response(care_reply, turn_id)
            DashboardStatsManager.record_result("Event acknowledged", success=True)
            return

        if not user_text:
            return

        self._last_turn_input = user_text
        self._current_turn_source = request.source
        self._current_turn_id = turn_id
        if request.source == "voice" and getattr(request, "transcription", None) is not None:
            vt = request.transcription
            self._last_turn_quality = vt.quality.decision if getattr(vt, "quality", None) else None
        else:
            self._last_turn_quality = None

        logger.info("[turn-%s] Started (source=%s): '%s'", turn_id, request.source, user_text)

        # Start structured activity feed block
        DashboardStatsManager.start_interaction(
            user_text, source=request.source, interaction_id=f"turn_{turn_id}"
        )
        raw_heard = request.raw_transcript or user_text
        DashboardStatsManager.record_heard(raw_heard)
        DashboardStatsManager.update("last_transcript", raw_heard)
        self.task_executor.reset_cancellation()
        self.computer_agent.reset_cancellation()

        try:
            # 0. Real-time Environment Observation
            ctx = self.environment_observer.refresh(force=True)

            # 1. Handle Pending Confirmation State (e.g. Delete Confirmation, Reminders, Shutdown)
            if ctx.pending_confirmation:
                pending = ctx.pending_confirmation
                ctx.pending_confirmation = None  # Clear state
                norm_lower = user_text.lower().strip()

                if norm_lower in ("yes", "ha", "haan", "sure", "do it", "confirm", "proceed", "yes please", "theek hai"):
                    action_type = pending.get("action")
                    if action_type == "SHUTDOWN_REQUEST":
                        DashboardStatsManager.record_understood("System Shutdown")
                        DashboardStatsManager.record_action("Shutting down NOVA")
                        self._deliver_response("Shutting down now. Goodbye Boss.", turn_id)
                        DashboardStatsManager.record_result("Shutdown initiated", success=True)
                        self._execute_local_shutdown()
                        return
                    elif action_type == "DELETE_ITEM":
                        target_p = pending.get("target_path")
                        if target_p and Path(target_p).exists():
                            DashboardStatsManager.record_understood("Delete Item", details={"Target": Path(target_p).name})
                            DashboardStatsManager.record_action(f"Deleting {Path(target_p).name}")
                            from desktop.files import FileSystemManager
                            success, msg = FileSystemManager.safe_move_to_trash(Path(target_p))
                            reply = f"Deleted {Path(target_p).name}." if success else f"Could not delete: {msg}"
                            self._deliver_response(reply, turn_id)
                            DashboardStatsManager.record_result(f"✓ Deleted {Path(target_p).name}" if success else f"✗ Delete failed: {msg}", success=success)
                            return
                    elif action_type == "REMINDER_REQUEST":
                        time_str = pending.get("time_str", "")
                        DashboardStatsManager.record_understood("Reminder Confirmed", details={"Time": time_str})
                        reply = f"Understood Boss. I've noted down your reminder for {time_str}."
                        self._deliver_response(reply, turn_id)
                        DashboardStatsManager.record_result(f"✓ Reminder set for {time_str}", success=True)
                        return
                elif norm_lower in ("no", "nah", "nahi", "cancel", "don't do it", "mat karo", "abort", "nevermind"):
                    DashboardStatsManager.record_understood("Action Cancelled")
                    self._deliver_response("Action cancelled, Boss.", turn_id)
                    DashboardStatsManager.record_result("Action cancelled by user", success=True)
                    return

            # 2. Local Voice Commands
            if self.command_router.route(user_text):
                DashboardStatsManager.record_understood("Local Voice Command")
                DashboardStatsManager.record_result("Command executed", success=True)
                return

            # 3. Layered Intent Classification & Routing with N-best Alternative Hypotheses
            candidates: list[str] = []
            if hasattr(request, "transcription") and request.transcription:
                candidates = list(getattr(request.transcription, "alternatives", []) or [])
            if request.raw_transcript and request.raw_transcript not in candidates:
                candidates.insert(0, request.raw_transcript)
            if user_text not in candidates:
                candidates.insert(0, user_text)

            structured_action = self.intent_engine.parse(user_text, allow_ai_fallback=False, candidates=candidates)
            norm_text = structured_action.normalized_input or user_text
            routing_domain = get_routing_domain(structured_action.intent)

            # 3A. Cancellation Actions ("Stop", "Cancel", "Never mind")
            if structured_action.intent == CanonicalIntent.CANCEL_ACTION:
                DashboardStatsManager.record_understood("Cancel Action")
                DashboardStatsManager.record_action("Stopping active tasks")
                self.task_executor.cancel_task()
                self.computer_agent.stop_active_task()
                self.desktop_manager.stop_active_task()
                if hasattr(self.browser_manager, "stop_active_task"):
                    self.browser_manager.stop_active_task()
                elif hasattr(self.browser_manager, "cancel_active_task"):
                    self.browser_manager.cancel_active_task()
                self._deliver_response("Stopped active tasks, Boss.", turn_id)
                DashboardStatsManager.record_result("✓ Active tasks stopped", success=True)
                return

            # 3B. Screen Recording Manager Actions
            if structured_action.intent == CanonicalIntent.START_SCREEN_RECORDING:
                logger.info("Detected START_SCREEN_RECORDING intent: '%s'", user_text)
                DashboardStatsManager.record_understood("Start Screen Recording")
                DashboardStatsManager.record_action("Starting screen recording")
                start_t = time.monotonic()
                res = self.screen_recording_manager.start_recording()
                lat_ms = (time.monotonic() - start_t) * 1000
                self._deliver_response(res.spoken_response, turn_id)
                DashboardStatsManager.record_result("● Screen recording started" if res.success else f"✗ Failed: {res.error}", success=res.success)
                DashboardStatsManager.record_mac_action(
                    command_text=user_text,
                    intent="system.screen_recording.start",
                    target="Screen",
                    status="RECORDING" if res.success else "FAILED",
                    latency_ms=lat_ms,
                    result_message=res.spoken_response,
                )
                return

            if structured_action.intent == CanonicalIntent.STOP_SCREEN_RECORDING:
                logger.info("Detected STOP_SCREEN_RECORDING intent: '%s'", user_text)
                DashboardStatsManager.record_understood("Stop Screen Recording")
                DashboardStatsManager.record_action("Stopping screen recording")
                start_t = time.monotonic()
                res = self.screen_recording_manager.stop_recording()
                lat_ms = (time.monotonic() - start_t) * 1000
                self._deliver_response(res.spoken_response, turn_id)
                DashboardStatsManager.record_result("✓ Screen recording stopped" if res.success else f"✗ Failed: {res.error}", success=res.success)
                DashboardStatsManager.record_mac_action(
                    command_text=user_text,
                    intent="system.screen_recording.stop",
                    target="Screen",
                    status="STOPPED" if res.success else "FAILED",
                    latency_ms=lat_ms,
                    result_message=res.spoken_response,
                )
                return

            # 3B-2. Screenshot Capture Action
            if structured_action.intent == CanonicalIntent.SCREEN_CAPTURE:
                logger.info("Detected screenshot intent: '%s'", user_text)
                DashboardStatsManager.record_understood("Screenshot")
                DashboardStatsManager.record_action("Capturing screen")
                start_t = time.monotonic()
                res = screenshot_service.capture_full_screen()
                lat_ms = (time.monotonic() - start_t) * 1000
                if res.success:
                    spoken = "Screenshot captured successfully and saved to your Desktop."
                    target_file = getattr(res, "file_path", None) or getattr(res, "saved_path", None)
                    saved_info = f"\nSaved to: {target_file}" if target_file else ""
                    DashboardStatsManager.record_verify(f"Screenshot saved to Desktop: {target_file}", success=True)
                    DashboardStatsManager.record_result(f"✓ Screenshot captured{saved_info}", success=True)
                else:
                    spoken = f"Sorry Boss, I couldn't take a screenshot: {res.error}"
                    DashboardStatsManager.record_verify(f"Screenshot failed: {res.error}", success=False)
                    DashboardStatsManager.record_result(f"✗ Screenshot failed: {res.error}", success=False)
                DashboardStatsManager.record_mac_action(
                    command_text=user_text,
                    intent="system.screenshot.capture",
                    target="Screen",
                    status="SUCCESS" if res.success else "FAILED",
                    latency_ms=lat_ms,
                    result_message=spoken,
                )
                self._deliver_response(spoken, turn_id)
                return

            # 3C. Visual / Computer Agent Actions
            if routing_domain == RoutingDomain.VISUAL:
                self.computer_agent.provider_mgr = self.provider_manager

                if structured_action.intent == CanonicalIntent.CLOSE_POPUP:
                    res = self.computer_agent.close_popup()
                    self._deliver_response(res.spoken_response, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.EXPLAIN_SCREEN_ERROR:
                    res = self.computer_agent.explain_active_screen_error()
                    self._deliver_response(res.spoken_response, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.SCROLL_UNTIL_VISIBLE:
                    tgt_text = structured_action.parameters.get("target_text", "")
                    res = self.computer_agent.scroll_until_visible(tgt_text)
                    self._deliver_response(res.spoken_response, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.TYPE_UI_TEXT:
                    text_val = structured_action.parameters.get("text", "")
                    tgt_lbl = structured_action.parameters.get("target_label")
                    res = self.computer_agent.type_into_focused_or_target(text_val, target_label=tgt_lbl)
                    self._deliver_response(res.spoken_response, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.CLICK_UI_ELEMENT:
                    tgt_lbl = structured_action.parameters.get("target_label", user_text)
                    res = self.computer_agent.execute_visual_goal(tgt_lbl)
                    self._deliver_response(res.spoken_response, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.WHAT_AM_I_LOOKING_AT:
                    app = ctx.active_application or "an application"
                    if ctx.current_url:
                        reply = f"You are currently viewing {ctx.current_page_title or ctx.current_domain or 'a webpage'} in {app}."
                    elif ctx.current_folder:
                        reply = f"You are currently looking at the {ctx.current_folder.name} folder in {app}."
                    elif ctx.active_window:
                        reply = f"You are looking at {ctx.active_window} in {app}."
                    else:
                        res = self.computer_agent.explain_screen_content()
                        reply = res.spoken_response
                    self._deliver_response(reply, turn_id)
                    return

            # 3D. Autonomous Multi-Step Task Agent Dispatch
            if routing_domain == RoutingDomain.TASK_AGENT or structured_action.intent == CanonicalIntent.AUTONOMOUS_TASK:
                self.task_planner.provider_mgr = self.provider_manager
                plan = self.task_planner.plan_goal(user_text)
                task_res = self.task_executor.execute_plan(plan, context=self.active_task_context)
                self._deliver_response(task_res.spoken_response, turn_id)
                return

            # 3E. Delete Item Safety Confirmation
            if structured_action.intent == CanonicalIntent.DELETE_ITEM:
                res = ContextResolver.resolve_target("this", ctx, target_type="any")
                if res["resolved"] and isinstance(res["target"], Path):
                    target_p = res["target"]
                    ctx.pending_confirmation = {
                        "action": "DELETE_ITEM",
                        "target_path": str(target_p),
                    }
                    spoken = f"Do you want me to delete {target_p.name}?"
                    self._deliver_response(spoken, turn_id)
                    return
                else:
                    spoken = "I couldn't identify which file or folder you want to delete. Please select an item first."
                    self._deliver_response(spoken, turn_id)
                    return

            # 3F. Reminder Request Clarification
            if structured_action.intent == CanonicalIntent.REMINDER_REQUEST:
                time_str = structured_action.parameters.get("time_str", "that time")
                ctx.pending_confirmation = {
                    "action": "REMINDER_REQUEST",
                    "time_str": time_str,
                    "original_request": user_text,
                }
                prompt = structured_action.clarification_prompt or f"Do you want me to remind you at {time_str}?"
                self._deliver_response(prompt, turn_id)
                return
            # 4. Domain-Aware Subsystem Dispatch
            if routing_domain == RoutingDomain.BROWSER:
                browser_result = self.browser_manager.execute_command(norm_text) or self.browser_manager.execute_command(user_text)
                if browser_result is not None:
                    self._deliver_response(browser_result.spoken_response, turn_id)
                    return
                # Scrolling fallback if browser command did not handle directly
                if structured_action.intent in (CanonicalIntent.SCROLL_DOWN, CanonicalIntent.SCROLL_UP, CanonicalIntent.SCROLL_TO_TOP, CanonicalIntent.SCROLL_TO_BOTTOM):
                    from browser.engine import MacOSNativeBrowserEngine
                    eng = MacOSNativeBrowserEngine()
                    if structured_action.intent == CanonicalIntent.SCROLL_TO_BOTTOM:
                        eng.scroll_to_bottom()
                        self._deliver_response("Scrolled to the bottom, Boss.", turn_id)
                    elif structured_action.intent == CanonicalIntent.SCROLL_TO_TOP:
                        eng.scroll_to_top()
                        self._deliver_response("Scrolled to the top, Boss.", turn_id)
                    elif structured_action.intent == CanonicalIntent.SCROLL_UP:
                        eng.scroll_page(direction="up")
                        self._deliver_response("Scrolled up, Boss.", turn_id)
                    else:
                        eng.scroll_page(direction="down")
                        self._deliver_response("Scrolled down, Boss.", turn_id)
                    return

            if routing_domain == RoutingDomain.DESKTOP_APP:
                if structured_action.intent == CanonicalIntent.OPEN_CAMERA:
                    DashboardStatsManager.record_understood("Open Camera", details={"Target": "Camera"})
                    DashboardStatsManager.record_action("Opening Camera")
                    res = self.desktop_manager.camera_mgr.open_camera()
                    DashboardStatsManager.record_result("✓ Camera opened" if res.success else f"✗ Failed: {res.message}", success=res.success)
                    self._deliver_response(res.spoken_response, turn_id)
                    return
                if structured_action.intent == CanonicalIntent.TAKE_PHOTO:
                    DashboardStatsManager.record_understood("Take Photo", details={"Target": "Camera"})
                    DashboardStatsManager.record_action("Capturing photo")
                    res = self.desktop_manager.camera_mgr.capture_photo()
                    DashboardStatsManager.record_result("✓ Photo captured" if res.success else f"✗ Failed: {res.message}", success=res.success)
                    self._deliver_response(res.spoken_response, turn_id)
                    return
                if structured_action.intent == CanonicalIntent.LAUNCH_APP:
                    app_name = structured_action.parameters.get("app_name", "")
                    DashboardStatsManager.record_understood("Open Application", details={"Target": app_name})
                    DashboardStatsManager.record_action(f"Opening {app_name}")
                    from desktop.apps import AppLauncher
                    start_t = time.monotonic()
                    success, msg, spoken = AppLauncher.launch(app_name)
                    lat_ms = (time.monotonic() - start_t) * 1000
                    if success:
                        DashboardStatsManager.record_verify(f"{app_name} opened and active", success=True)
                        DashboardStatsManager.record_result(f"{app_name} launched successfully.", success=True)
                        try:
                            if hasattr(self, "active_task_context") and self.active_task_context:
                                if hasattr(self.active_task_context, "register_application"):
                                    self.active_task_context.register_application(app_name)
                                elif hasattr(self.active_task_context, "register_app"):
                                    self.active_task_context.register_app(app_name)
                        except Exception as bookkeeping_err:
                            logger.warning("Failed post-launch bookkeeping for %s: %s", app_name, bookkeeping_err)
                    else:
                        DashboardStatsManager.record_result(f"Failed to open {app_name}: {msg}", success=False)
                    DashboardStatsManager.record_mac_action(
                        command_text=user_text,
                        intent="application.open",
                        target=app_name,
                        status="SUCCESS" if success else "FAILED",
                        latency_ms=lat_ms,
                        result_message=spoken,
                    )
                    self._deliver_response(spoken, turn_id)
                    return
                if structured_action.intent == CanonicalIntent.CLOSE_APP:
                    app_name = structured_action.parameters.get("app_name", "")
                    DashboardStatsManager.record_understood("Close Application", details={"Target": app_name})
                    DashboardStatsManager.record_action(f"Closing {app_name}")
                    from desktop.apps import AppLauncher
                    start_t = time.monotonic()
                    success, msg, spoken = AppLauncher.close(app_name)
                    lat_ms = (time.monotonic() - start_t) * 1000
                    if success:
                        DashboardStatsManager.record_result(f"✓ {app_name} closed", success=True)
                    else:
                        DashboardStatsManager.record_result(f"✗ Failed to close {app_name}: {msg}", success=False)
                    DashboardStatsManager.record_mac_action(
                        command_text=user_text,
                        intent="application.close",
                        target=app_name,
                        status="SUCCESS" if success else "FAILED",
                        latency_ms=lat_ms,
                        result_message=spoken,
                    )
                    self._deliver_response(spoken, turn_id)
                    return

            if routing_domain in (RoutingDomain.FILESYSTEM, RoutingDomain.DOCUMENT_WRITING, RoutingDomain.DESKTOP_APP):
                if structured_action.intent == CanonicalIntent.GENERATE_AND_WRITE_DOCUMENT or routing_domain == RoutingDomain.DOCUMENT_WRITING:
                    from desktop.editor import DocumentEditor
                    topic = structured_action.parameters.get("topic") or structured_action.parameters.get("content") or user_text
                    fname = structured_action.parameters.get("filename", "document.txt")
                    dest = structured_action.parameters.get("destination", "Notepad")
                    DashboardStatsManager.record_understood(
                        "WRITE",
                        details={
                            "Destination": dest,
                            "Content": f'"{topic}"',
                            "Confidence": f"{int(structured_action.confidence * 100)}%",
                        },
                    )
                    DashboardStatsManager.record_action(f"Writing content to {dest}")
                    desktop_result = DocumentEditor.write_and_open_document(
                        topic=topic,
                        filename=fname,
                        destination=dest,
                    )
                    if desktop_result.success:
                        DashboardStatsManager.record_verify(f"{dest} content written successfully", success=True)
                        DashboardStatsManager.record_result(f"✓ Written to {dest}", success=True)
                    else:
                        DashboardStatsManager.record_verify(f"Failed to write to {dest}: {desktop_result.error}", success=False)
                        DashboardStatsManager.record_result(f"✗ Write failed: {desktop_result.error}", success=False)
                    self._deliver_response(desktop_result.spoken_response, turn_id)
                    return

                desktop_result = self.desktop_manager.process_input(norm_text) or self.desktop_manager.process_input(user_text)
                if desktop_result is not None:
                    if desktop_result.success and desktop_result.target_path:
                        tp = Path(desktop_result.target_path)
                        if tp.is_dir():
                            self.active_task_context.register_folder(tp.name, tp)
                        elif tp.is_file():
                            self.active_task_context.register_file(tp.name, tp)
                    self._deliver_response(desktop_result.spoken_response, turn_id)
                    return

            if routing_domain == RoutingDomain.SYSTEM:
                if structured_action.intent == CanonicalIntent.GET_CLIPBOARD:
                    try:
                        from mac_control.actions.clipboard import get_clipboard
                        clip_text = get_clipboard()
                        spoken = f"Your clipboard contains: {clip_text[:120]}" if clip_text else "Your clipboard is currently empty."
                    except Exception:
                        spoken = "I could not access the clipboard."
                    self._deliver_response(spoken, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.CLEAR_CLIPBOARD:
                    try:
                        from mac_control.actions.clipboard import clear_clipboard
                        clear_clipboard()
                        spoken = "Clipboard cleared, Boss."
                    except Exception:
                        spoken = "Failed to clear clipboard."
                    self._deliver_response(spoken, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.SET_CLIPBOARD:
                    try:
                        from mac_control.actions.clipboard import set_clipboard
                        text_to_set = structured_action.parameters.get("text", "")
                        if structured_action.parameters.get("use_context"):
                            if ctx.current_url:
                                text_to_set = ctx.current_url
                            elif ctx.last_created_path:
                                text_to_set = str(ctx.last_created_path)
                        set_clipboard(text_to_set)
                        spoken = "Copied to clipboard, Boss."
                    except Exception:
                        spoken = "Failed to set clipboard."
                    self._deliver_response(spoken, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.CONTROL_WIFI:
                    act = structured_action.parameters.get("action", "status")
                    und_name = "Wi-Fi Control" if act in ("on", "off") else ("Get Wi-Fi Network" if act == "ssid" else ("Get Network Details" if act == "details" else "Get Wi-Fi Status"))
                    act_desc = "Turning Wi-Fi on" if act == "on" else ("Turning Wi-Fi off" if act == "off" else ("Checking Wi-Fi network" if act == "ssid" else ("Checking network details" if act == "details" else "Checking Wi-Fi status")))
                    DashboardStatsManager.record_understood(und_name, details={"Intent": "network.wifi", "Action": act, "Target": "Wi-Fi"})
                    DashboardStatsManager.record_action(act_desc)
                    try:
                        from mac_control.actions.wifi import execute_wifi_command
                        from mac_control.models import MacCommand, CommandCategory
                        cmd = MacCommand(category=CommandCategory.NETWORK, action=act, raw_input=user_text)
                        res = execute_wifi_command(cmd)
                        spoken = res.message
                        is_succ = (res.status.value == "SUCCESS")
                        DashboardStatsManager.record_verify(f"Wi-Fi verified: {spoken}", success=is_succ)
                        DashboardStatsManager.record_result(spoken, success=is_succ)
                        DashboardStatsManager.record_mac_action(
                            command_text=user_text,
                            intent="network.wifi",
                            target="Wi-Fi",
                            status="SUCCESS" if is_succ else "FAILED",
                            latency_ms=res.execution_time_ms,
                            result_message=spoken,
                        )
                    except Exception as exc:
                        logger.error("Wi-Fi control error: %s", exc, exc_info=True)
                        spoken = f"Boss, I couldn't control Wi-Fi because: {exc}"
                        DashboardStatsManager.record_result(f"Failed: {exc}", success=False)
                        DashboardStatsManager.record_mac_action(
                            command_text=user_text,
                            intent="network.wifi",
                            target="Wi-Fi",
                            status="FAILED",
                            result_message=str(exc),
                        )
                    self._deliver_response(spoken, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.CONTROL_BLUETOOTH:
                    act = structured_action.parameters.get("action", "status")
                    und_name = "Bluetooth Control" if act in ("on", "off") else ("Get Bluetooth Devices" if act in ("devices", "connected", "which", "list") else "Get Bluetooth Status")
                    act_desc = "Turning Bluetooth on" if act == "on" else ("Turning Bluetooth off" if act == "off" else ("Checking connected Bluetooth devices" if act in ("devices", "connected", "which", "list") else "Checking Bluetooth status"))
                    DashboardStatsManager.record_understood(und_name, details={"Intent": "network.bluetooth", "Action": act, "Target": "Bluetooth"})
                    DashboardStatsManager.record_action(act_desc)
                    try:
                        from mac_control.actions.bluetooth import execute_bluetooth_command
                        from mac_control.models import MacCommand, CommandCategory
                        cmd = MacCommand(category=CommandCategory.NETWORK, action=act, raw_input=user_text)
                        res = execute_bluetooth_command(cmd)
                        spoken = res.message
                        is_succ = (res.status.value == "SUCCESS")
                        DashboardStatsManager.record_verify(f"Bluetooth verified: {spoken}", success=is_succ)
                        DashboardStatsManager.record_result(spoken, success=is_succ)
                        DashboardStatsManager.record_mac_action(
                            command_text=user_text,
                            intent="network.bluetooth",
                            target="Bluetooth",
                            status="SUCCESS" if is_succ else "FAILED",
                            latency_ms=res.execution_time_ms,
                            result_message=spoken,
                        )
                    except Exception as exc:
                        logger.error("Bluetooth control error: %s", exc, exc_info=True)
                        spoken = f"Boss, I couldn't control Bluetooth because: {exc}"
                        DashboardStatsManager.record_result(f"Failed: {exc}", success=False)
                        DashboardStatsManager.record_mac_action(
                            command_text=user_text,
                            intent="network.bluetooth",
                            target="Bluetooth",
                            status="FAILED",
                            result_message=str(exc),
                        )
                    self._deliver_response(spoken, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.LOCK_SCREEN:
                    try:
                        from mac_control.actions.system import lock_screen
                        lock_screen()
                        spoken = "Screen locked, Boss."
                    except Exception:
                        spoken = "Failed to lock screen."
                    self._deliver_response(spoken, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.SYSTEM_SHUTDOWN:
                    is_uncertain = (self._current_turn_source == "voice" and getattr(self, "_last_turn_quality", None) == QualityDecision.UNCERTAIN)
                    if is_uncertain:
                        ctx.pending_confirmation = {"action": "SHUTDOWN_REQUEST"}
                        self._deliver_response("I heard 'shutdown'. Did you mean shut down NOVA?", turn_id)
                        return
                    self._execute_local_shutdown()
                    return

                if structured_action.intent == CanonicalIntent.CONTROL_BRIGHTNESS:
                    from mac_control.actions.brightness import execute_brightness_command
                    from mac_control.models import MacCommand, CommandCategory
                    act = structured_action.parameters.get("action", "increase")
                    val = structured_action.parameters.get("value")
                    und_details = {"Target": "Mac display"}
                    if val is not None:
                        und_details["Value"] = f"{val}%"
                    und_name = "Set Brightness" if act == "set" else ("Increase Brightness" if act == "increase" else ("Decrease Brightness" if act == "decrease" else "Get Brightness"))
                    DashboardStatsManager.record_understood(und_name, details=und_details)
                    act_desc = f"Setting brightness to {val}%" if act == "set" and val is not None else ("Increasing brightness" if act == "increase" else ("Decreasing brightness" if act == "decrease" else f"{act.title()}ing brightness"))
                    DashboardStatsManager.record_action(act_desc)
                    args = {k: v for k, v in structured_action.parameters.items() if k != "action"}
                    cmd = MacCommand(
                        category=CommandCategory.BRIGHTNESS,
                        action=act,
                        args=args,
                        raw_input=user_text,
                    )
                    start_t = time.monotonic()
                    res = execute_brightness_command(cmd)
                    lat_ms = (time.monotonic() - start_t) * 1000
                    is_succ = (res.status.value == "SUCCESS")
                    if is_succ:
                        actual_bright = res.details.get("actual_value", val) if res.details else val
                        if val is None and act == "increase":
                            res_msg = "Brightness increased successfully."
                            spoken = "Done Boss. Brightness increased."
                        elif val is None and act == "decrease":
                            res_msg = "Brightness decreased successfully."
                            spoken = "Done Boss. Brightness decreased."
                        elif actual_bright is not None:
                            res_msg = f"Brightness is now {actual_bright}%."
                            spoken = f"Done Boss. Brightness is now {actual_bright}%."
                        else:
                            res_msg = f"{res.message} successfully." if not res.message.endswith("successfully.") else res.message
                            spoken = f"Done Boss. {res.message}."
                        DashboardStatsManager.record_verify(f"Actual screen brightness: {actual_bright}%" if actual_bright is not None else "Brightness adjusted", success=True)
                        DashboardStatsManager.record_result(res_msg, success=True)
                    else:
                        DashboardStatsManager.record_verify(f"Brightness adjustment failed: {res.message}", success=False)
                        DashboardStatsManager.record_result(f"Failed: {res.message}", success=False)
                        spoken = f"Sorry Boss, I couldn't adjust the brightness: {res.message}"
                    DashboardStatsManager.record_mac_action(
                        command_text=user_text,
                        intent=f"system.brightness.{act}",
                        target="Brightness",
                        status="SUCCESS" if is_succ else "FAILED",
                        latency_ms=lat_ms,
                        result_message=spoken,
                    )
                    self._deliver_response(spoken, turn_id)
                    return

                if structured_action.intent == CanonicalIntent.CONTROL_VOLUME:
                    from mac_control.actions.volume import execute_volume_command
                    from mac_control.models import MacCommand, CommandCategory
                    act = structured_action.parameters.get("action", "increase")
                    val = structured_action.parameters.get("value")
                    und_details = {"Target": "System audio"}
                    if val is not None:
                        und_details["Value"] = f"{val}%"
                    und_name = "Set Volume" if act == "set" else ("Increase Volume" if act == "increase" else ("Decrease Volume" if act == "decrease" else ("Mute Audio" if act == "mute" else ("Unmute Audio" if act == "unmute" else "Get Volume"))))
                    DashboardStatsManager.record_understood(und_name, details=und_details)
                    act_desc = f"Setting volume to {val}%" if act == "set" and val is not None else ("Increasing volume" if act == "increase" else ("Decreasing volume" if act == "decrease" else ("Muting volume" if act == "mute" else ("Unmuting volume" if act == "unmute" else f"{act.title()}ing volume"))))
                    DashboardStatsManager.record_action(act_desc)
                    args = {k: v for k, v in structured_action.parameters.items() if k != "action"}
                    cmd = MacCommand(
                        category=CommandCategory.VOLUME,
                        action=act,
                        args=args,
                        raw_input=user_text,
                    )
                    start_t = time.monotonic()
                    res = execute_volume_command(cmd)
                    lat_ms = (time.monotonic() - start_t) * 1000
                    is_succ = (res.status.value == "SUCCESS")
                    if is_succ:
                        actual_vol = res.details.get("actual_value", val) if res.details else val
                        if val is None and act == "increase":
                            res_msg = "Volume increased successfully."
                            spoken = "Done Boss. Volume increased."
                        elif val is None and act == "decrease":
                            res_msg = "Volume decreased successfully."
                            spoken = "Done Boss. Volume decreased."
                        elif act in ("mute", "unmute"):
                            res_msg = f"{res.message} successfully." if not res.message.endswith("successfully.") else res.message
                            spoken = f"Done Boss. {res.message}."
                        elif actual_vol is not None:
                            res_msg = f"Volume is now {actual_vol}%."
                            spoken = f"Done Boss. Volume is now {actual_vol}%."
                        else:
                            res_msg = f"{res.message} successfully." if not res.message.endswith("successfully.") else res.message
                            spoken = f"Done Boss. {res.message}."
                        DashboardStatsManager.record_verify(f"Actual system volume: {actual_vol}%" if actual_vol is not None else "Volume adjusted", success=True)
                        DashboardStatsManager.record_result(res_msg, success=True)
                    else:
                        DashboardStatsManager.record_verify(f"Volume adjustment failed: {res.message}", success=False)
                        DashboardStatsManager.record_result(f"Failed: {res.message}", success=False)
                        spoken = f"Sorry Boss, I couldn't adjust the volume: {res.message}"
                    DashboardStatsManager.record_mac_action(
                        command_text=user_text,
                        intent=f"system.volume.{act}",
                        target="Volume",
                        status="SUCCESS" if is_succ else "FAILED",
                        latency_ms=lat_ms,
                        result_message=spoken,
                    )
                    self._deliver_response(spoken, turn_id)
                    return

            # Fallback checks across Desktop and Browser
            desktop_result = self.desktop_manager.process_input(user_text)
            if desktop_result is not None:
                self._deliver_response(desktop_result.spoken_response, turn_id)
                return

            browser_result = self.browser_manager.execute_command(user_text)
            if browser_result is not None:
                self._deliver_response(browser_result.spoken_response, turn_id)
                return

            # 3. Semantic Analysis & Context
            if self.emotion_engine is None:
                self.emotion_engine = EmotionEngine()
            if self.system_prompt_manager is None:
                self.system_prompt_manager = SystemPromptManager()
            if self.provider_manager is None:
                from providers.provider_manager import ProviderManager
                self.provider_manager = ProviderManager()

            DashboardStatsManager.record_understood("Conversational Query")
            analysis: ConversationAnalysis = self.emotion_engine.analyze_text(user_text)
            memory_summary = self._build_memory_summary(user_text)
            task_type = self._map_mode_to_task_type(analysis.detected_mode)
            profile_name = self._map_mode_to_profile(analysis.detected_mode)
            active_provider = self._peek_active_provider(task_type)

            self.event_bus.publish(NovaEvent.THINKING_STARTED, text=user_text)

            context = PromptBuildContext(
                memory_summary=memory_summary,
                current_project=self.activity.current_project,
                current_task=self.activity.current_task,
                emotion=analysis.emotion_description,
                current_provider=active_provider,
                voice_mode=(request.source == "voice"),
                audio_event=request.audio_event,
            )

            DashboardStatsManager.update("active_provider", active_provider or "Gemini")

            # 4. LLM Response Generation
            gen_start = time.monotonic()
            response_text = self._generate_response(user_text, context, profile_name, task_type, turn_id)
            gen_elapsed = time.monotonic() - gen_start
            DashboardStatsManager.update("latency", f"{gen_elapsed:.2f}s")

            if response_text is None:
                DashboardStatsManager.record_error("No response generated from AI providers")
                return

            self.event_bus.publish(
                NovaEvent.RESPONSE_GENERATED, text=response_text, provider=active_provider
            )

            # 5. Write to Durable Memory if needed
            if self._should_remember(user_text, analysis):
                self._write_memory(user_text, response_text, analysis)

            # 6. Update Ephemeral History
            self._conversation_history.append({"role": "user", "content": user_text})
            self._conversation_history.append({"role": "assistant", "content": response_text})
            self.activity.last_conversation_topic = user_text[:200]

            # 7. Deliver Response (Console Output + Voice V2 Speaking)
            self._deliver_response(response_text, turn_id)
            DashboardStatsManager.record_result("Conversation completed", success=True)

        except Exception as exc:
            logger.error("[turn-%s] Error processing turn: %s", turn_id, exc, exc_info=True)
            DashboardStatsManager.record_error(f"Issue processing request: {exc}")
            self._deliver_response("Sorry Boss, I encountered an issue processing that.", turn_id)
        finally:
            if self.voice_available and hasattr(self, "voice_manager") and self.voice_manager is not None:
                if self.voice_manager.state == VoiceState.PROCESSING:
                    self.voice_manager.set_state(VoiceState.LISTENING)
            logger.info("[turn-%s] Turn finished.", turn_id)

    def _generate_response(
        self,
        user_text: str,
        context: PromptBuildContext,
        profile_name: str,
        task_type: TaskType,
        turn_id: str,
    ) -> str | None:
        """Build system prompt and invoke ProviderManager."""
        assert self.system_prompt_manager is not None
        assert self.provider_manager is not None

        try:
            prompt_text = self.system_prompt_manager.build_prompt(profile=profile_name, context=context)
        except ProfileNotFoundError:
            prompt_text = self.system_prompt_manager.build_prompt(
                profile=ProfileName.DEFAULT.value, context=context
            )

        if self._conversation_history:
            history_lines = []
            for msg in self._conversation_history[-10:]:
                role = "User" if msg["role"] == "user" else "Assistant"
                history_lines.append(f"{role}: {msg['content']}")
            prompt_text += "\n\n## Recent Conversation History\n" + "\n".join(history_lines) + "\n"

        override_provider = self._manual_provider_override
        self._manual_provider_override = None

        if context.voice_mode:
            lowered = user_text.lower()
            if task_type in (TaskType.CODING, TaskType.REASONING) or any(
                k in lowered for k in ("explain", "how does", "what is", "teach me", "difference between", "why", "concept", "algorithm")
            ):
                max_tokens = 500
            elif any(lowered.startswith(k) for k in ("hello", "hi", "hey", "good morning", "are you there", "how are you")):
                max_tokens = 120
            else:
                max_tokens = 250
        else:
            max_tokens = None
        from core.response_cleaner import clean_model_response

        try:
            if override_provider:
                raw_res = self.provider_manager.generate_response(
                    prompt=user_text,
                    system_prompt=prompt_text,
                    task_type=task_type,
                    mode="manual",
                    provider_name=override_provider,
                    max_tokens=max_tokens,
                )
                return clean_model_response(raw_res)
            raw_res = self.provider_manager.generate_response(
                prompt=user_text,
                system_prompt=prompt_text,
                task_type=task_type,
                mode="auto",
                max_tokens=max_tokens,
            )
            return clean_model_response(raw_res)
        except AllProvidersFailedError as exc:
            logger.error("[turn-%s] All AI providers failed: %s", turn_id, exc)
            self._deliver_response("I'm having trouble reaching my AI engines right now, Boss.", turn_id)
            return None

    def _deliver_response(self, text: str, turn_id: str) -> None:
        """Deliver response text through console and speech."""
        from core.response_cleaner import clean_model_response
        clean_text = clean_model_response(text)
        DashboardStatsManager.record_nova(clean_text)

        print(f"NOVA: {clean_text}")

        # Speak via Voice V2
        if self.voice_available:
            self.voice_manager.speak(clean_text)

    def _peek_active_provider(self, task_type: TaskType) -> str | None:
        if self.provider_manager is None:
            return None
        try:
            return self.provider_manager.choose_provider(task_type=task_type, mode="auto").provider_name
        except Exception:
            return None

    def _build_memory_summary(self, query_text: str) -> str | None:
        import re
        q = query_text.lower().strip()
        cleaned_q = re.sub(r"[^\w\s]", "", q)
        # Avoid pulling memory dumps during greetings, pleasantries, or simple conversational turns
        simple_greetings = (
            "hello", "hi", "hey", "how are you", "good morning", "good afternoon",
            "good evening", "good night", "are you there", "you there", "thank you",
            "thanks", "whats up", "what is up", "sup", "how is it going", "hows it going",
            "who are you", "what can you do", "nice to meet you"
        )
        if cleaned_q in simple_greetings or (len(cleaned_q.split()) <= 4 and any(cleaned_q.startswith(p) for p in ("hello", "hi ", "hey ", "good morning", "are you there", "thank"))):
            return None

        parts: list[str] = []
        if self.memory_manager is not None:
            try:
                for entry in self.memory_manager.search_memory(query=query_text)[:3]:
                    val = str(entry.value).replace("\n", " ")
                    if len(val) > 80:
                        val = val[:77] + "..."
                    parts.append(f"{entry.category.value}: {val}")
            except Exception:
                pass
        if self.vector_store is not None and len(cleaned_q.split()) > 3:
            try:
                for result in self.vector_store.search(query_text, top_k=2):
                    doc_txt = str(result.document.text).replace("\n", " ")
                    if len(doc_txt) > 80:
                        doc_txt = doc_txt[:77] + "..."
                    parts.append(doc_txt)
            except Exception:
                pass
        return "; ".join(parts) if parts else None

    def _should_remember(self, user_text: str, analysis: ConversationAnalysis) -> bool:
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

    def _write_memory(self, user_text: str, response_text: str, analysis: ConversationAnalysis) -> None:
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
            except Exception as exc:
                logger.warning("Failed to write memory entry: %s", exc)

        if self.vector_store is not None:
            try:
                self.vector_store.add_document(
                    text=turn_summary,
                    category=category.value,
                    tags=(analysis.detected_mode.value,),
                )
            except Exception:
                pass

    @staticmethod
    def _map_mode_to_task_type(mode: ConversationMode) -> TaskType:
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

    def _execute_local_shutdown(self) -> None:
        """Handle shutdown command from voice or local input cleanly."""
        self._is_already_shutting_down = True
        farewell = "See you soon Boss."

        print("\n----------------------------------------")
        print("👤 YOU:", getattr(self, "_last_turn_input", "shutdown"))
        print("🟢 Shutdown command confirmed.")
        print("💾 Saving memory...")

        session_length = datetime.now(timezone.utc) - self.activity.session_start_time
        summary = (
            f"project={self.activity.current_project or 'none'}; "
            f"topic={self.activity.last_conversation_topic or 'none'}; "
            f"session_length={session_length}"
        )
        self._write_breadcrumb(summary)

        if self.memory_manager is not None:
            try:
                self.memory_manager.shutdown()
            except Exception:
                pass

        print("🎤 Stopping Voice V2...")
        if self.voice_available:
            try:
                self.voice_manager.stop_listening()
            except Exception:
                pass

        print(f"\nNOVA: {farewell}")
        print("----------------------------------------\n")
        if self.voice_available:
            try:
                self.voice_manager.speak(farewell)
            except Exception:
                pass
            try:
                self.voice_manager.shutdown()
            except Exception:
                pass

        if self.provider_manager is not None:
            try:
                self.provider_manager.shutdown()
            except Exception:
                pass

        try:
            self.browser_manager.shutdown()
        except Exception:
            pass

        try:
            lifecycle.shutdown()
        except Exception:
            pass

        print("🟢 Session closed.")
        sys.exit(0)

    def _execute_local_cancel(self) -> None:
        """Immediate local cancellation callback."""
        self.task_executor.cancel_task()
        self.computer_agent.stop_active_task()
        self.desktop_manager.stop_active_task()
        if hasattr(self.browser_manager, "stop_active_task"):
            self.browser_manager.stop_active_task()
        elif hasattr(self.browser_manager, "cancel_active_task"):
            self.browser_manager.cancel_active_task()
        logger.info("Local cancellation executed.")
        self._deliver_response("Stopped active tasks, Boss.", getattr(self, "_current_turn_id", "local_cancel"))

    def _shutdown(self) -> None:
        """Tear down all subsystems gracefully."""
        if self._is_already_shutting_down:
            return
        self._is_already_shutting_down = True
        logger.info("NOVA shutdown initiated.")

        try:
            self.event_bus.publish(NovaEvent.APPLICATION_SHUTDOWN)
        except Exception:
            pass

        if self.voice_available:
            try:
                self.voice_manager.shutdown()
            except Exception as exc:
                logger.error("Error shutting down VoiceManager: %s", exc)

        try:
            self.browser_manager.shutdown()
        except Exception as exc:
            logger.error("Error shutting down BrowserManager: %s", exc)

        try:
            self.computer_agent.eyes.stop()
        except Exception as exc:
            logger.debug("Error stopping NOVA Eyes: %s", exc)

        if self.provider_manager is not None:
            try:
                self.provider_manager.shutdown()
            except Exception as exc:
                logger.error("Error shutting down ProviderManager: %s", exc)

        if self.system_prompt_manager is not None:
            try:
                self.system_prompt_manager.shutdown()
            except Exception as exc:
                logger.error("Error shutting down SystemPromptManager: %s", exc)

        if self.memory_manager is not None:
            try:
                self.memory_manager.shutdown()
            except Exception as exc:
                logger.error("Error shutting down MemoryManager: %s", exc)

        try:
            lifecycle.shutdown()
        except Exception as exc:
            logger.error("Error during lifecycle shutdown: %s", exc)

        logger.info("NOVA has shut down.")


def main() -> int:
    """Construct and run a NOVA application instance."""
    if len(sys.argv) > 1 and sys.argv[1] == "doctor":
        try:
            from ui.doctor import Doctor

            doc = Doctor()
            return doc.run()
        except Exception as exc:
            print(f"Failed to execute doctor diagnostics: {exc}")
            return 1

    app = NovaApplication()
    return app.run()


if __name__ == "__main__":
    sys.exit(main())