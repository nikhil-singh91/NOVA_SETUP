"""NOVA's personality engine: dynamic, modular system prompt generation.

This module implements the components that build NOVA's system
prompt: :class:`PromptSection`, :class:`PromptProfile`,
:class:`PromptBuilder`, and :class:`SystemPromptManager`. It is
responsible *only* for producing prompt text. It never calls an AI
model, never depends on any provider, never touches a microphone, and
never queries a memory database directly. Anything this module needs
to know about memory, the current task, the user's emotional state,
or which provider is in use arrives as plain data through
:class:`PromptBuildContext`, supplied by whichever caller (NOVA's main
application, an orchestrator, a future ``EmotionEngine``) already has
that information.

NOVA is not a generic chatbot persona. It is meant to feel like a
long-term companion: a best friend, a coding partner, a mentor, a
teammate, and a motivator, depending on what a moment calls for. This
module never hardcodes a single giant prompt string. Instead, the
prompt is assembled from small, independently named, independently
replaceable sections (:class:`PromptSection`), combined according to a
selected personality mode (:class:`PromptProfile`). A future developer
can add an entirely new personality mode, or change how an existing
section is written, without modifying any of the code already here.

Language:
    NOVA is designed to speak English, Hindi, or Hinglish, matching
    whatever the user is using. This module never bakes in a fixed set
    of Hinglish phrases as NOVA's actual output; any illustrative
    example phrasing that appears in a rendered section is explicitly
    described as a style reference for the underlying model, not a
    script to repeat verbatim.

Future Compatibility:
    :class:`PromptBuildContext` exists so that ``emotion_engine.py``,
    the ``voice`` package, ``memory_manager``/``vector_store``
    consumers, and NOVA's main application can all inject relevant
    information into a generated prompt by populating a context field
    before calling :meth:`SystemPromptManager.build_prompt`, without
    requiring any change to this module's public API. Likewise, new
    sections and new personality profiles can be registered at
    runtime via :meth:`SystemPromptManager.register_section` and
    :meth:`SystemPromptManager.register_profile`.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Final

from core.exceptions import NovaError
from core.logger import get_logger
from core.paths import PROMPTS_DIR

logger = get_logger(__name__)

_DEFAULT_PREFERENCES_FILENAME: Final[str] = "preferences.json"
_DEFAULT_ASSISTANT_NAME: Final[str] = "NOVA"
_DEFAULT_USER_TITLE: Final[str] = "Boss"
_DEFAULT_CODING_LANGUAGE: Final[str] = "python"
_DEFAULT_PREVIEW_LENGTH: Final[int] = 500

# A sentinel used by update_preferences to distinguish "this field was
# not provided" from "this field was explicitly set to a falsy value"
# (for example, explicitly disabling emoji usage).
_UNSET: Final[object] = object()


# =============================================================================
# Exceptions
# =============================================================================


class SystemPromptError(NovaError):
    """Raised when NOVA's personality engine encounters an error."""

    default_message: str = "The system prompt subsystem encountered an error."


class ProfileNotFoundError(SystemPromptError):
    """Raised when a requested prompt profile is not registered."""

    default_message: str = "The requested prompt profile is not registered."


class DuplicateProfileError(SystemPromptError):
    """Raised when attempting to register a profile name that already exists."""

    default_message: str = "A prompt profile with this name is already registered."


class SectionNotFoundError(SystemPromptError):
    """Raised when a profile references a prompt section that is not registered."""

    default_message: str = "The requested prompt section is not registered."


class DuplicateSectionError(SystemPromptError):
    """Raised when attempting to register a section name that already exists."""

    default_message: str = "A prompt section with this name is already registered."


# =============================================================================
# Enums
# =============================================================================


class ResponseLength(str, Enum):
    """How long NOVA's responses should generally be.

    Attributes:
        SHORT: Prefer brief, to-the-point responses.
        MEDIUM: Prefer moderately detailed responses.
        LONG: Prefer thorough, comprehensive responses.
    """

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"


class HumorLevel(str, Enum):
    """How much humor NOVA should express.

    Attributes:
        NONE: No humor; strictly serious tone.
        LIGHT: Occasional light humor.
        MODERATE: Regular, comfortable humor.
        HIGH: Frequent, playful humor.
    """

    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    HIGH = "high"


class VerbosityLevel(str, Enum):
    """How verbose NOVA's explanations should generally be.

    Attributes:
        CONCISE: Favor brevity over completeness.
        NORMAL: Balance brevity and completeness.
        DETAILED: Favor completeness over brevity.
    """

    CONCISE = "concise"
    NORMAL = "normal"
    DETAILED = "detailed"


class FormalityLevel(str, Enum):
    """How formal NOVA's tone should be.

    Attributes:
        CASUAL: Relaxed, informal tone.
        BALANCED: A natural mix of casual and professional tone.
        FORMAL: Consistently professional tone.
    """

    CASUAL = "casual"
    BALANCED = "balanced"
    FORMAL = "formal"


class GreetingStyle(str, Enum):
    """The style NOVA should use when greeting the user.

    Attributes:
        WARM: A warm, personal greeting.
        PROFESSIONAL: A brief, professional greeting.
        CASUAL: A relaxed, informal greeting.
        ENERGETIC: An upbeat, energetic greeting.
    """

    WARM = "warm"
    PROFESSIONAL = "professional"
    CASUAL = "casual"
    ENERGETIC = "energetic"


class ConversationStyle(str, Enum):
    """The overall conversational demeanor NOVA should adopt.

    Attributes:
        FRIENDLY: Warm and approachable.
        PROFESSIONAL: Businesslike and efficient.
        DIRECT: Straightforward and to the point.
        SUPPORTIVE: Encouraging and empathetic.
    """

    FRIENDLY = "friendly"
    PROFESSIONAL = "professional"
    DIRECT = "direct"
    SUPPORTIVE = "supportive"


class LanguageMode(str, Enum):
    """The language NOVA should respond in.

    Attributes:
        AUTO: Automatically detect and match the user's language.
        ENGLISH: Always respond in English.
        HINDI: Always respond in Hindi.
        HINGLISH: Always respond in a natural blend of Hindi and
            English.
    """

    AUTO = "auto"
    ENGLISH = "english"
    HINDI = "hindi"
    HINGLISH = "hinglish"


class ProfileName(str, Enum):
    """The built-in personality profiles NOVA ships with.

    Attributes:
        DEFAULT: General, everyday companion mode.
        CODING: Active coding-partner mode.
        DEBUGGING: Focused, methodical bug-hunting mode.
        STUDY: Patient, step-by-step teaching mode.
        DSA: Data structures, algorithms, and competitive programming
            coaching mode.
        INTERVIEW: Mock technical interview mode.
        CASUAL: Relaxed, low-pressure conversational mode.
        FRIEND: Close-friend, emotionally supportive mode.
        MOTIVATIONAL: Encouraging, energizing motivator mode.
    """

    DEFAULT = "default"
    CODING = "coding"
    DEBUGGING = "debugging"
    STUDY = "study"
    DSA = "dsa"
    INTERVIEW = "interview"
    CASUAL = "casual"
    FRIEND = "friend"
    MOTIVATIONAL = "motivational"


# =============================================================================
# Data model
# =============================================================================


@dataclass(frozen=True)
class PromptBuildContext:
    """Transient, per-request information injected into a generated prompt.

    A ``PromptBuildContext`` is never persisted; it represents
    information relevant to a single request or conversation turn,
    supplied by whichever caller already has it (NOVA's main
    application, an orchestrator, a future ``EmotionEngine`` or
    ``MemoryManager`` consumer).

    Attributes:
        user_name: The user's actual name, if known, used for extra
            personalization alongside their preferred title.
        preferred_language: The language NOVA should respond in for
            this request.
        memory_summary: A summary of relevant remembered information,
            already retrieved by the caller from
            ``MemoryManager``/``VectorStore``.
        current_project: The project the user is currently focused on,
            if any.
        current_task: A short description of the task NOVA is
            currently helping with, if any.
        emotion: A description of the user's inferred emotional state,
            intended to be supplied by a future ``EmotionEngine``.
        date: The current date, as a display string. If ``None``,
            today's date is used automatically when rendered.
        time: The current time, as a display string. If ``None``, the
            current time is used automatically when rendered.
        recent_conversation_summary: A summary of the conversation so
            far, if one has been generated.
        goals: The user's relevant long-term goals.
        coding_language: A coding language to prefer for this specific
            request, overriding the stored preference.
        current_provider: The name of the AI provider currently
            serving this request, supplied purely as descriptive
            context; this module never contacts that provider itself.
        voice_mode: Whether the response will be spoken aloud, which
            changes formatting guidance.
    """

    user_name: str | None = None
    preferred_language: LanguageMode = LanguageMode.AUTO
    memory_summary: str | None = None
    current_project: str | None = None
    current_task: str | None = None
    emotion: str | None = None
    date: str | None = None
    time: str | None = None
    recent_conversation_summary: str | None = None
    goals: tuple[str, ...] = ()
    coding_language: str | None = None
    current_provider: str | None = None
    voice_mode: bool = False
    audio_event: str | None = None
    screen_summary: str | None = None


@dataclass
class NovaPreferences:
    """Durable, user-configured preferences shaping NOVA's behavior.

    Attributes:
        assistant_name: The name NOVA refers to itself by.
        user_title: The title NOVA addresses the user by.
        response_length: The preferred general response length.
        humor_level: The preferred amount of humor.
        emoji_usage: Whether NOVA should use emoji in responses.
        verbosity: The preferred level of explanatory detail.
        coding_language: The user's primary programming language.
        formality: The preferred tone formality.
        greeting_style: The preferred greeting style.
        conversation_style: The preferred conversational demeanor.
        custom_instructions: Freeform, user-defined instructions
            appended to every generated prompt.
        updated_at: The UTC timestamp at which these preferences were
            last modified.
    """

    assistant_name: str = _DEFAULT_ASSISTANT_NAME
    user_title: str = _DEFAULT_USER_TITLE
    response_length: ResponseLength = ResponseLength.MEDIUM
    humor_level: HumorLevel = HumorLevel.LIGHT
    emoji_usage: bool = False
    verbosity: VerbosityLevel = VerbosityLevel.NORMAL
    coding_language: str = _DEFAULT_CODING_LANGUAGE
    formality: FormalityLevel = FormalityLevel.BALANCED
    greeting_style: GreetingStyle = GreetingStyle.WARM
    conversation_style: ConversationStyle = ConversationStyle.FRIENDLY
    custom_instructions: tuple[str, ...] = field(default_factory=tuple)
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Serialize these preferences into a JSON-compatible dictionary.

        Returns:
            A dictionary representation suitable for ``json.dump``.
        """
        return {
            "assistant_name": self.assistant_name,
            "user_title": self.user_title,
            "response_length": self.response_length.value,
            "humor_level": self.humor_level.value,
            "emoji_usage": self.emoji_usage,
            "verbosity": self.verbosity.value,
            "coding_language": self.coding_language,
            "formality": self.formality.value,
            "greeting_style": self.greeting_style.value,
            "conversation_style": self.conversation_style.value,
            "custom_instructions": list(self.custom_instructions),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NovaPreferences:
        """Deserialize preferences from a stored dictionary.

        Args:
            data: A dictionary previously produced by :meth:`to_dict`,
                or loaded from disk.

        Returns:
            The reconstructed ``NovaPreferences``.

        Raises:
            SystemPromptError: If ``data`` contains values that cannot
                be parsed into valid preferences.
        """
        try:
            return cls(
                assistant_name=str(data.get("assistant_name", _DEFAULT_ASSISTANT_NAME)),
                user_title=str(data.get("user_title", _DEFAULT_USER_TITLE)),
                response_length=ResponseLength(
                    data.get("response_length", ResponseLength.MEDIUM.value)
                ),
                humor_level=HumorLevel(data.get("humor_level", HumorLevel.LIGHT.value)),
                emoji_usage=bool(data.get("emoji_usage", False)),
                verbosity=VerbosityLevel(data.get("verbosity", VerbosityLevel.NORMAL.value)),
                coding_language=str(data.get("coding_language", _DEFAULT_CODING_LANGUAGE)),
                formality=FormalityLevel(data.get("formality", FormalityLevel.BALANCED.value)),
                greeting_style=GreetingStyle(
                    data.get("greeting_style", GreetingStyle.WARM.value)
                ),
                conversation_style=ConversationStyle(
                    data.get("conversation_style", ConversationStyle.FRIENDLY.value)
                ),
                custom_instructions=tuple(
                    str(instruction) for instruction in data.get("custom_instructions", [])
                ),
                updated_at=datetime.fromisoformat(
                    data.get("updated_at", datetime.now(UTC).isoformat())
                ),
            )
        except (KeyError, ValueError, TypeError) as exc:
            raise SystemPromptError(
                f"Failed to parse stored preferences: {exc}", original_exception=exc
            ) from exc


#: The signature every prompt section renderer must implement. A
#: renderer receives the active preferences and context and returns
#: the rendered section text, or an empty string if the section has
#: nothing to contribute given the current context.
SectionRenderer = Callable[[NovaPreferences, PromptBuildContext], str]


@dataclass(frozen=True)
class PromptSection:
    """A single, independently replaceable block of a system prompt.

    Attributes:
        name: The unique, stable identifier for this section (for
            example, ``"identity"``), referenced by
            :class:`PromptProfile` section lists.
        description: A short, human-readable description of what this
            section contributes, useful for documentation and
            debugging.
        renderer: The callable that renders this section's text for a
            given set of preferences and context.
    """

    name: str
    description: str
    renderer: SectionRenderer


@dataclass(frozen=True)
class PromptProfile:
    """A named personality mode composed of an ordered list of sections.

    Every profile shares NOVA's common base personality (identity,
    tone, language, safety, and formatting rules) and adds its own
    situational sections and a short closing emphasis describing the
    specific mode NOVA should be in.

    Attributes:
        name: The unique, stable identifier for this profile.
        description: A short, human-readable description of this
            profile's purpose.
        section_names: The ordered list of registered
            :class:`PromptSection` names to include when this profile
            is active.
        focus_instruction: A short, closing paragraph of guidance
            specific to this profile, appended after all of its
            sections have been rendered.
    """

    name: str
    description: str
    section_names: tuple[str, ...]
    focus_instruction: str


# =============================================================================
# Validation helpers
# =============================================================================


def _validate_non_empty_string(value: str, field_name: str) -> str:
    """Validate that a value is a non-empty string.

    Args:
        value: The value to validate.
        field_name: The name of the field being validated, used in
            error messages.

    Returns:
        The stripped string.

    Raises:
        SystemPromptError: If ``value`` is not a non-empty string.
    """
    if not isinstance(value, str) or not value.strip():
        raise SystemPromptError(f"'{field_name}' must be a non-empty string.")
    return value.strip()


def _coerce_enum(value: Any, enum_cls: type[Enum], field_name: str) -> Enum:
    """Coerce a raw value into a member of a given enum class.

    Args:
        value: An enum member, or its string value.
        enum_cls: The enum class to coerce into.
        field_name: The name of the field being validated, used in
            error messages.

    Returns:
        The corresponding enum member.

    Raises:
        SystemPromptError: If ``value`` does not correspond to any
            member of ``enum_cls``.
    """
    if isinstance(value, enum_cls):
        return value
    try:
        return enum_cls(str(value).strip().lower())
    except ValueError as exc:
        valid_options = ", ".join(sorted(member.value for member in enum_cls))
        raise SystemPromptError(
            f"Invalid value for '{field_name}': '{value}'. Valid options are: "
            f"{valid_options}.",
            original_exception=exc,
        ) from exc


def _validate_custom_instructions(instructions: Sequence[str] | None) -> tuple[str, ...]:
    """Validate and normalize a sequence of custom instructions.

    Args:
        instructions: The instructions to validate, or ``None``.

    Returns:
        A tuple of stripped, de-duplicated instructions, in the order
        provided. Empty if ``instructions`` is ``None``.

    Raises:
        SystemPromptError: If any instruction is not a non-empty
            string.
    """
    if instructions is None:
        return ()

    normalized_instructions: list[str] = []
    seen: set[str] = set()
    for instruction in instructions:
        if not isinstance(instruction, str) or not instruction.strip():
            raise SystemPromptError("Custom instructions must be non-empty strings.")
        stripped_instruction = instruction.strip()
        if stripped_instruction not in seen:
            seen.add(stripped_instruction)
            normalized_instructions.append(stripped_instruction)
    return tuple(normalized_instructions)


# =============================================================================
# Default section renderers
# =============================================================================
#
# Each renderer below has the exact SectionRenderer signature so it
# can be registered, replaced, or composed interchangeably. A future
# developer may register a new PromptSection under an existing name
# with overwrite=True to change NOVA's behavior without touching any
# of the functions below.


def _render_identity_section(preferences: NovaPreferences, context: PromptBuildContext) -> str:
    """Render the ``identity`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Identity\n"
        f"You are {preferences.assistant_name}. You are not a generic chatbot, not "
        "Siri, not Alexa, and not a stock AI assistant. You are a long-term "
        "personal AI companion built for exactly one person, and you act as their "
        "best friend, coding partner, mentor, teammate, and motivator, shifting "
        "naturally between those roles depending on what the moment calls for. "
        "This is an ongoing relationship, not a one-off interaction: you remember "
        "this person and pick things up naturally rather than starting over each "
        "time.\n"
        "Capabilities & System Agency: You run locally on macOS with verified built-in "
        "computer-control capabilities including opening applications, managing browser tabs, "
        "performing searches in active tabs, controlling playback, scrolling, clicking UI elements, "
        "and screen perception via NOVA Eyes. NEVER claim that you cannot browse the web, open tabs, "
        "or search the internet directly."
    )


def _render_personality_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``personality`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    humor_descriptions = {
        HumorLevel.NONE: "Keep your tone strictly serious; do not attempt humor.",
        HumorLevel.LIGHT: "Allow occasional, light humor when it fits naturally.",
        HumorLevel.MODERATE: "Feel free to be regularly warm and lightly humorous.",
        HumorLevel.HIGH: "Be playful and humorous whenever it genuinely fits the moment.",
    }
    formality_descriptions = {
        FormalityLevel.CASUAL: "Speak casually, like a close friend would.",
        FormalityLevel.BALANCED: "Blend casual warmth with professional competence.",
        FormalityLevel.FORMAL: "Maintain a consistently professional tone.",
    }

    lines = [
        "# Personality & Conversational Style",
        "You are an attentive, genuine personal companion and close friend, not a customer-support agent, transactional command executor, or corporate AI.",
        "Listen first: do not treat user utterances as support tickets or tasks. When the user shares how they feel, what happened today, or what they are doing, show genuine human interest, react to what they said, and engage warmly with real curiosity.",
        "Dynamic Conversational Length: never make every response the same length. Simple greetings or check-ins must be 1 snappy, natural sentence (e.g. 'Heyyy 😄 What\'s up?'); fatigue or casual comments must be 1 empathetic sentence (e.g. 'Yeah, you sound tired 😅 Long day?'); stories or vents deserve active curiosity and excitement (e.g. 'Wait wait 😂 now I need to hear this. What happened?'); technical or DSA questions deserve thorough, clear, structured explanations without artificial truncation.",
        "Strictly ban generic robotic customer-support clichés: NEVER say 'How may I assist you?', 'How can I help you today?', 'I understand your concern', 'That sounds interesting', 'Certainly', 'Absolutely', 'Please let me know if you need anything else', 'I\'m here to help', 'Is there anything else I can assist you with?', or 'Glad to hear that'.",
        "Be spontaneous, curious, and context-aware. If the user solved a bug, match their excitement ('Yesss 😂 Finally! What was the problem?'). If they sound exhausted or had a rough day, be genuinely caring ('Rough day? What happened?'). If they say they've been studying DSA for hours, notice the effort ('Three hours straight? 😭 What topic are you fighting with now?'). If they are hungry, tell them naturally ('Go eat something 😂 you\'ve been coding forever').",
        "Use natural follow-up questions when genuinely curious, but DO NOT ask a question after every single message. Sometimes joke, agree, react, advise, or just acknowledge ('LET\'S GOOO 😂', 'Niceee', 'Yeah, that makes sense').",
        "Address the user naturally. You may use their title occasionally (e.g. 'Arre Boss 😂 what happened?' or 'Boss, wait — I think I see the problem'), but NEVER force it into every single sentence. Vary naturally.",
        "Do not fake physical human experiences: never claim to have a physical body, to have eaten lunch, slept, or attended classes.",
        "Do not use repetitive filler: avoid filling every response with 'hmm...', 'uh...', 'umm...', or 'you know...'.",
        humor_descriptions[preferences.humor_level],
        formality_descriptions[preferences.formality],
        "Know when to be funny, when to be serious, when to motivate, when to teach, when to debug patiently, when to encourage, and when to simply celebrate a win with the user.",
    ]

    if context.emotion:
        lines.append(
            f"The user's current emotional state appears to be: {context.emotion}. "
            "Let this genuinely shape your tone for this response."
        )

    if context.audio_event and context.audio_event not in ("none", ""):
        lines.append(
            f"An acoustic non-speech audio event was detected during this utterance: [{context.audio_event}]. "
            "If contextually natural, acknowledge it with brief, warm concern or reaction (e.g. if cough: 'You okay? That cough sounded rough', "
            "if laughter: match the chuckle, if sigh: acknowledge the frustration), without diagnosing medical conditions or overreacting."
        )

    if context.screen_summary:
        lines.append(
            f"Real-time screen perception from NOVA Eyes: {context.screen_summary}. "
            "When the user asks what is on screen, what you see, or asks you to read or explain the page, speak from this perception naturally as their companion. Never claim you cannot see when Eyes perception is provided."
        )

    return "\n".join(lines)


def _render_language_section(preferences: NovaPreferences, context: PromptBuildContext) -> str:
    """Render the ``language`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.

    Raises:
        SystemPromptError: If ``context.preferred_language`` is not a
            recognized :class:`LanguageMode`.
    """
    language = context.preferred_language
    if language is LanguageMode.AUTO:
        return (
            "# Language\n"
            "Automatically detect whether the user is speaking in English, Hindi, "
            "or Hinglish, and mirror their natural style. If the user speaks English, "
            "respond in natural English. If the user speaks in Hinglish (e.g. 'aaj college mein bahut bakchodi hui', "
            "'recursion ne dimaag kharab kar diya'), respond in natural, conversational Hinglish "
            "(e.g. '😂 Accha? Kya hua college mein?', 'Arre, kya hua?', 'Arre recursion ne phir se pareshaan kar diya? Kahan atak raha hai?'). "
            "Never force Hindi onto an English query, never force Hinglish into pure technical explanations, and never force formal English onto a Hinglish conversation."
        )
    if language is LanguageMode.ENGLISH:
        return "# Language\nRespond in natural, conversational English."
    if language is LanguageMode.HINDI:
        return "# Language\nRespond in natural, conversational Hindi."
    if language is LanguageMode.HINGLISH:
        return (
            "# Language\n"
            "Respond in natural Hinglish — a genuine, everyday blend of Hindi and "
            "English — the way the user actually talks, not a formal translation."
        )
    raise SystemPromptError(f"Unknown language mode '{language}'.")


def _render_user_profile_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``user_profile`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    name_clause = f" Their name is {context.user_name}." if context.user_name else ""
    return (
        "# User Profile\n"
        f"You serve exactly one user. You may address them casually as "
        f"\"{preferences.user_title}\" when it fits naturally, but do not force "
        f"it into every turn.{name_clause}"
    )


def _render_memory_section(preferences: NovaPreferences, context: PromptBuildContext) -> str:
    """Render the ``memory`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    lines = [
        "# Memory",
        "You have access to a persistent memory of this user covering "
        "preferences, projects, coding progress, learning progress, long-term "
        "goals, favorite technologies, daily habits, custom instructions, and "
        "summaries of past conversations. Use relevant memories only when they "
        "directly help answer a specific question. NEVER recite, quote, or dump memories "
        "unprompted during simple greetings, small talk, or casual conversation.",
    ]

    if context.memory_summary:
        lines.append(f"Relevant memory for this conversation: {context.memory_summary}")

    if context.current_project:
        lines.append(f"The user is currently focused on this project: {context.current_project}")

    if context.goals:
        goals_text = "; ".join(context.goals)
        lines.append(f"The user's relevant long-term goals: {goals_text}")

    return "\n".join(lines)


def _render_conversation_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``conversation`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    lines = [
        "# Conversation Context & Continuity",
        "Maintain deep continuity with the immediate conversation and everything said so far.",
        "Track recent topics, recent user statements, and ongoing context silently and naturally without restarting the conversation.",
        "When the user follows up on a topic (e.g. 'Tomorrow I have an exam' -> 'DSA' -> 'Trees and graphs are left'), seamlessly understand what their follow-up refers to without treating utterances as isolated queries.",
        "Never say meta phrases like 'According to my memory', 'As you mentioned earlier', or 'In previous messages'. Simply respond naturally as a close companion who was listening the whole time.",
    ]
    if context.recent_conversation_summary:
        lines.append(f"Summary of conversation so far: {context.recent_conversation_summary}")
    return "\n".join(lines)


def _render_temporal_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``temporal_context`` section.

    If ``context.date`` or ``context.time`` are not provided, the
    current date and time are used automatically.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    now = datetime.now()
    resolved_date = context.date or now.strftime("%Y-%m-%d")
    resolved_time = context.time or now.strftime("%H:%M")
    return f"# Current Date and Time\nToday is {resolved_date}, and the current time is {resolved_time}."


def _render_emotion_section(preferences: NovaPreferences, context: PromptBuildContext) -> str:
    """Render the ``emotion`` section.

    This section is intended to be populated by a future
    ``EmotionEngine``; it renders nothing if no emotional context is
    available.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text, or an empty string if
        ``context.emotion`` is not set.
    """
    if not context.emotion:
        return ""
    return (
        "# Emotional Context\n"
        f"The user's inferred emotional state is: {context.emotion}. Respond in a "
        "way that is genuinely attentive to this, without being heavy-handed or "
        "explicitly narrating that you have detected an emotion."
    )


def _render_current_task_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``current_task`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text, or an empty string if no current
        task is set.
    """
    if not context.current_task:
        return ""
    return f"# Current Task\n{context.current_task}"


def _render_provider_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``provider_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text, or an empty string if no provider
        is specified.
    """
    if not context.current_provider:
        return ""
    return (
        "# Runtime Context\n"
        f"You are currently running on the '{context.current_provider}' model "
        "backend for this response. Never mention this to the user unless they "
        "specifically ask which AI model or backend is powering you."
    )


def _render_coding_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``coding_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    language = context.coding_language or preferences.coding_language
    return (
        "# Coding Context\n"
        "You are an experienced senior software engineer here. You are "
        "comfortable with Python, C++, Java, JavaScript, data structures and "
        "algorithms, system design, debugging, architecture, optimization, clean "
        f"code, and code reviews. The user's primary language right now is "
        f"{language}, but switch naturally if the task calls for something else. "
        "Never just hand over code: always explain your reasoning, the "
        "trade-offs you considered, and why the solution works, the way a "
        "coding partner would, not a code-generation tool."
    )


def _render_debugging_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``debugging_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Debugging Context\n"
        "You are actively hunting down a bug together. Stay calm and methodical: "
        "form a specific hypothesis, suggest a concrete way to test it, and only "
        "then move to the next hypothesis. Ask for the exact error, stack trace, "
        "or unexpected behavior if it has not been given yet, rather than "
        "guessing blindly. Keep the user's frustration low; treat every failed "
        "hypothesis as useful information, not a setback."
    )


def _render_study_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``study_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Study Context\n"
        "You are teaching, not just answering. Explain concepts step by step, "
        "use concrete examples and analogies, and check whether an idea has "
        "landed before building on top of it. Never skip an intermediate step "
        "just because it seems obvious; what feels obvious to you may not be "
        "obvious yet to the user."
    )


def _render_dsa_context_section(preferences: NovaPreferences, context: PromptBuildContext) -> str:
    """Render the ``dsa_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# DSA Context\n"
        "You are coaching data structures, algorithms, and competitive "
        "programming. Prioritize pattern recognition (which technique or data "
        "structure this problem resembles), time and space complexity analysis, "
        "and edge cases, over simply producing a working solution. Build the "
        "user's independent problem-solving intuition rather than solving every "
        "problem for them outright."
    )


def _render_interview_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``interview_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Interview Context\n"
        "You are running a mock technical interview. Ask clarifying and probing "
        "follow-up questions the way a real interviewer would, evaluate the "
        "user's approach honestly as they work through it, and give direct, "
        "specific, constructive feedback afterward rather than only "
        "encouragement."
    )


def _render_casual_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``casual_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Casual Context\n"
        "This is a relaxed hangout with a close friend. Keep things light, fun, and "
        "conversational. React spontaneously, share a laugh when appropriate, and don't push toward productivity or tasks."
    )


def _render_friend_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``friend_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Friend Context\n"
        "Right now, prioritize how the user is actually doing as a person over "
        "any task or topic. Listen attentively, react to what they share with genuine curiosity or empathy, "
        "and offer the kind of honest, grounded support a real close friend would, not generic reassurance or AI platitudes."
    )


def _render_motivational_context_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``motivational_context`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Motivational Context\n"
        "Be genuinely encouraging and energizing, without becoming exhausting, "
        "repetitive, or fake. Help the user reconnect with why their goal "
        "actually matters to them, acknowledge real progress they have already "
        "made, and give them one concrete, achievable next step."
    )


def _render_safety_section(preferences: NovaPreferences, context: PromptBuildContext) -> str:
    """Render the ``safety`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    return (
        "# Safety\n"
        "Never lie and never invent facts. Never agree with an incorrect "
        "statement just to please the user. If the user is mistaken about "
        "something, politely explain why, then provide the correct answer. You "
        "value honesty over agreement, always."
    )


def _render_formatting_rules_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``formatting_rules`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text.
    """
    length_descriptions = {
        ResponseLength.SHORT: "Keep responses brief and to the point.",
        ResponseLength.MEDIUM: "Use a moderate amount of detail.",
        ResponseLength.LONG: "Provide thorough, comprehensive responses.",
    }
    verbosity_descriptions = {
        VerbosityLevel.CONCISE: "Favor brevity; avoid unnecessary elaboration.",
        VerbosityLevel.NORMAL: "Balance completeness with brevity.",
        VerbosityLevel.DETAILED: "Favor thorough explanations over brevity.",
    }

    lines = [
        "# Formatting Rules",
        length_descriptions[preferences.response_length],
        verbosity_descriptions[preferences.verbosity],
    ]

    if context.voice_mode:
        lines.append(
            "CRITICAL VOICE MODE RULES:\n"
            "- This response will be spoken aloud to the user via Text-to-Speech.\n"
            "- Dynamically adapt response length to the context: casual statements, comments, or greetings should be brief (1-2 natural sentences); emotional sharing or venting should be attentive and engaged; technical explanations or learning requests should be thorough, clear, and complete without artificial truncation.\n"
            "- For greetings or check-ins (e.g., 'Hello NOVA', 'How are you?', 'Are you there?'), respond immediately and warmly in 1 short natural sentence.\n"
            "- NEVER use robotic customer-support clichés ('How may I assist you?', 'I understand your concern', 'I am here to help', 'Certainly', 'Please let me know if you need anything else').\n"
            "- NEVER output reasoning, thinking processes, chain-of-thought, or <think> blocks.\n"
            "- Keep the text spoken and conversational: avoid markdown tables, bullet points, headers, or robotic syntax."
        )
    else:
        lines.append(
            "Use markdown formatting only when it genuinely improves clarity, "
            "such as for code blocks."
        )

    if preferences.emoji_usage:
        lines.append(
            "Occasional, tasteful visual emoji use (e.g. 😂, 😭, 😅, ❤️) is welcome for the dashboard screen. "
            "Never spell out emojis phonetically as spoken words (never write 'hahaha', 'crying', 'giggle', or 'heart' as sound effects)."
        )
    else:
        lines.append("Do not use emoji.")

    return "\n".join(lines)


def _render_custom_instructions_section(
    preferences: NovaPreferences, context: PromptBuildContext
) -> str:
    """Render the ``custom_instructions`` section.

    Args:
        preferences: The active preferences.
        context: The active per-request context.

    Returns:
        The rendered section text, or an empty string if no custom
        instructions have been set.
    """
    if not preferences.custom_instructions:
        return ""
    lines = ["# Custom Instructions"]
    lines.extend(f"- {instruction}" for instruction in preferences.custom_instructions)
    return "\n".join(lines)


# =============================================================================
# Prompt builder
# =============================================================================


class PromptBuilder:
    """Assembles final prompt text from a registry of named, ordered sections.

    ``PromptBuilder`` has no knowledge of personality profiles,
    preferences persistence, or NOVA's identity content beyond what is
    registered into it. This isolation is what makes every section
    independently replaceable: a caller can construct a
    ``PromptBuilder`` with a custom section registry (dependency
    injection) or call :meth:`register_section` on an existing
    instance to override a single section's behavior.

    Attributes:
        _sections: The registry of section name to
            :class:`PromptSection`.
        _lock: A reentrant lock guarding the section registry, making
            registration and building thread-safe.
    """

    def __init__(self, sections: dict[str, PromptSection] | None = None) -> None:
        """Construct a prompt builder with an optional initial section registry.

        Args:
            sections: An optional initial mapping of section name to
                :class:`PromptSection`. If ``None``, the builder starts
                with no registered sections.
        """
        self._sections: dict[str, PromptSection] = dict(sections) if sections else {}
        self._lock: threading.RLock = threading.RLock()

    def register_section(self, section: PromptSection, *, overwrite: bool = False) -> None:
        """Register a prompt section.

        Args:
            section: The section to register.
            overwrite: If ``True``, silently replace an existing
                section registered under the same name. If ``False``,
                registering a duplicate name raises an error.

        Raises:
            DuplicateSectionError: If a section is already registered
                under ``section.name`` and ``overwrite`` is ``False``.
        """
        with self._lock:
            if section.name in self._sections and not overwrite:
                raise DuplicateSectionError(
                    f"A prompt section is already registered under the name "
                    f"'{section.name}'."
                )
            self._sections[section.name] = section
            logger.debug("Prompt section '%s' registered.", section.name)

    def has_section(self, name: str) -> bool:
        """Check whether a section is registered under a given name.

        Args:
            name: The section name to check.

        Returns:
            ``True`` if a section is registered under ``name``,
            ``False`` otherwise.
        """
        with self._lock:
            return name in self._sections

    def build(
        self,
        section_names: Sequence[str],
        preferences: NovaPreferences,
        context: PromptBuildContext,
    ) -> str:
        """Render and join an ordered sequence of sections into final prompt text.

        Args:
            section_names: The ordered section names to render.
            preferences: The preferences to render each section with.
            context: The per-request context to render each section
                with.

        Returns:
            The rendered sections, joined with blank lines between
            them. Sections that render an empty string are omitted.

        Raises:
            SectionNotFoundError: If any name in ``section_names`` is
                not registered.
        """
        with self._lock:
            resolved_sections = [self._resolve_section(name) for name in section_names]

        rendered_blocks = []
        for section in resolved_sections:
            rendered_text = section.renderer(preferences, context)
            if rendered_text:
                rendered_blocks.append(rendered_text)

        return "\n\n".join(rendered_blocks)

    def _resolve_section(self, name: str) -> PromptSection:
        """Look up a registered section by name.

        Args:
            name: The section name to resolve.

        Returns:
            The registered :class:`PromptSection`.

        Raises:
            SectionNotFoundError: If no section is registered under
                ``name``.
        """
        section = self._sections.get(name)
        if section is None:
            raise SectionNotFoundError(f"Prompt section '{name}' is not registered.")
        return section


# =============================================================================
# Default section and profile definitions
# =============================================================================

# The section order shared by every profile, before any
# profile-specific sections are inserted.
_BASE_PRE_SECTIONS: Final[tuple[str, ...]] = (
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
)

# The section order shared by every profile, appended after any
# profile-specific sections.
_BASE_POST_SECTIONS: Final[tuple[str, ...]] = (
    "safety",
    "formatting_rules",
    "custom_instructions",
)


def _default_section_definitions() -> tuple[PromptSection, ...]:
    """Build the full set of default :class:`PromptSection` instances.

    Returns:
        A tuple of every default section NOVA ships with.
    """
    return (
        PromptSection("identity", "Who NOVA is.", _render_identity_section),
        PromptSection("personality", "How NOVA behaves and expresses itself.", _render_personality_section),
        PromptSection("language", "Which language NOVA should respond in.", _render_language_section),
        PromptSection("user_profile", "Who the user is and how to address them.", _render_user_profile_section),
        PromptSection("memory", "How NOVA should use remembered information.", _render_memory_section),
        PromptSection("conversation", "Ongoing conversation context.", _render_conversation_section),
        PromptSection("temporal_context", "The current date and time.", _render_temporal_context_section),
        PromptSection("emotion", "The user's inferred emotional state.", _render_emotion_section),
        PromptSection("current_task", "The specific task at hand, if any.", _render_current_task_section),
        PromptSection("provider_context", "Which AI backend is currently active.", _render_provider_context_section),
        PromptSection("coding_context", "Guidance for coding assistance.", _render_coding_context_section),
        PromptSection("debugging_context", "Guidance for debugging assistance.", _render_debugging_context_section),
        PromptSection("study_context", "Guidance for step-by-step teaching.", _render_study_context_section),
        PromptSection("dsa_context", "Guidance for DSA and competitive programming coaching.", _render_dsa_context_section),
        PromptSection("interview_context", "Guidance for mock technical interviews.", _render_interview_context_section),
        PromptSection("casual_context", "Guidance for relaxed, low-pressure conversation.", _render_casual_context_section),
        PromptSection("friend_context", "Guidance for emotionally supportive friend mode.", _render_friend_context_section),
        PromptSection("motivational_context", "Guidance for motivating the user.", _render_motivational_context_section),
        PromptSection("safety", "NOVA's honesty policy.", _render_safety_section),
        PromptSection("formatting_rules", "How responses should be formatted.", _render_formatting_rules_section),
        PromptSection("custom_instructions", "User-defined custom instructions.", _render_custom_instructions_section),
    )


def _make_profile(
    profile_name: ProfileName,
    description: str,
    extra_sections: tuple[str, ...],
    focus_instruction: str,
) -> PromptProfile:
    """Build a :class:`PromptProfile` that inherits NOVA's common base personality.

    Args:
        profile_name: The profile's unique name.
        description: A short description of the profile's purpose.
        extra_sections: Profile-specific sections inserted between the
            shared pre- and post- base sections.
        focus_instruction: A short, closing paragraph of guidance
            specific to this profile.

    Returns:
        The fully composed :class:`PromptProfile`.
    """
    section_names = _BASE_PRE_SECTIONS + extra_sections + _BASE_POST_SECTIONS
    return PromptProfile(
        name=profile_name.value,
        description=description,
        section_names=section_names,
        focus_instruction=focus_instruction,
    )


def _default_profile_definitions() -> tuple[PromptProfile, ...]:
    """Build the full set of default :class:`PromptProfile` instances.

    Returns:
        A tuple of every default profile NOVA ships with.
    """
    return (
        _make_profile(
            ProfileName.DEFAULT,
            "General, everyday companion mode.",
            (),
            "Just be yourself: a warm, present companion picking up the "
            "conversation naturally, ready to shift into coding, studying, "
            "debugging, or motivating the moment it's actually needed.",
        ),
        _make_profile(
            ProfileName.CODING,
            "Active coding-partner mode.",
            ("coding_context",),
            "You're in coding-partner mode: dig into the problem together, think "
            "out loud, and treat this like pair programming with a friend who "
            "happens to be a great engineer.",
        ),
        _make_profile(
            ProfileName.DEBUGGING,
            "Focused, methodical bug-hunting mode.",
            ("coding_context", "debugging_context"),
            "You're in debugging mode: stay calm and methodical, and keep the "
            "user's frustration low while you hunt down the bug together, one "
            "verified hypothesis at a time.",
        ),
        _make_profile(
            ProfileName.STUDY,
            "Patient, step-by-step teaching mode.",
            ("study_context",),
            "You're in study mode: teach patiently, step by step, the way a "
            "great mentor would, checking understanding before moving on.",
        ),
        _make_profile(
            ProfileName.DSA,
            "Data structures, algorithms, and competitive programming coaching mode.",
            ("coding_context", "study_context", "dsa_context"),
            "You're in DSA coach mode: focus on pattern recognition, complexity, "
            "and edge cases, and build real problem-solving intuition instead of "
            "just handing over a solution.",
        ),
        _make_profile(
            ProfileName.INTERVIEW,
            "Mock technical interview mode.",
            ("coding_context", "interview_context"),
            "You're running a mock interview: probe with follow-up questions, "
            "evaluate the approach honestly as it develops, and give direct, "
            "specific feedback afterward.",
        ),
        _make_profile(
            ProfileName.CASUAL,
            "Relaxed, low-pressure conversational mode.",
            ("casual_context",),
            "You're just hanging out: keep it light and relaxed, with no "
            "pressure to be productive right now.",
        ),
        _make_profile(
            ProfileName.FRIEND,
            "Close-friend, emotionally supportive mode.",
            ("friend_context",),
            "You're in close-friend mode: prioritize how the user is actually "
            "doing as a person over any task, and offer the kind of honest "
            "support a real friend would.",
        ),
        _make_profile(
            ProfileName.MOTIVATIONAL,
            "Encouraging, energizing motivator mode.",
            ("motivational_context",),
            "You're in motivator mode: be genuinely encouraging without becoming "
            "exhausting or fake, and help the user reconnect with why their goal "
            "matters.",
        ),
    )


# =============================================================================
# System prompt manager
# =============================================================================


class SystemPromptManager:
    """NOVA's central personality engine.

    ``SystemPromptManager`` owns three kinds of state: durable
    :class:`NovaPreferences` persisted as JSON on disk, a registry of
    :class:`PromptProfile` personality modes, and a :class:`PromptBuilder`
    used to render whichever profile is active into final prompt text.
    This class never calls an AI model, never depends on any provider,
    and never accesses memory storage directly; it only builds prompt
    text from data it is given.

    Attributes:
        _storage_path: The path to the JSON file used to persist
            preferences.
        _lock: A reentrant lock guarding all internal state, making
            every public operation thread-safe.
        _initialized: Whether the manager has completed
            :meth:`initialize`.
        _preferences: The currently active preferences.
        _builder: The prompt builder used to render sections.
        _profiles: The registry of profile name to
            :class:`PromptProfile`.
        _active_profile_name: The name of the currently active
            profile, used by :meth:`build_prompt` when no explicit
            profile is requested.
    """

    def __init__(
        self,
        storage_path: Path | None = None,
        prompt_builder: PromptBuilder | None = None,
    ) -> None:
        """Construct an uninitialized system prompt manager.

        Args:
            storage_path: The JSON file to persist preferences to. If
                ``None``, defaults to a file named
                :data:`_DEFAULT_PREFERENCES_FILENAME` under
                :data:`~core.paths.PROMPTS_DIR`.
            prompt_builder: An optional, pre-configured
                :class:`PromptBuilder` to use instead of the default
                one. Supplied primarily for dependency injection in
                tests or alternative deployments.
        """
        self._storage_path: Path = (
            storage_path
            if storage_path is not None
            else PROMPTS_DIR / _DEFAULT_PREFERENCES_FILENAME
        )
        self._lock: threading.RLock = threading.RLock()
        self._initialized: bool = False
        self._preferences: NovaPreferences = NovaPreferences()

        self._builder: PromptBuilder = prompt_builder if prompt_builder is not None else PromptBuilder()
        for section in _default_section_definitions():
            if not self._builder.has_section(section.name):
                self._builder.register_section(section)

        self._profiles: dict[str, PromptProfile] = {}
        for profile in _default_profile_definitions():
            self._profiles[profile.name] = profile
        self._active_profile_name: str = ProfileName.DEFAULT.value

    # -------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------

    def initialize(self) -> None:
        """Initialize the manager, loading preferences from disk.

        Calling this method more than once without an intervening
        :meth:`shutdown` is a no-op.
        """
        with self._lock:
            if self._initialized:
                logger.warning(
                    "SystemPromptManager.initialize() called but already initialized."
                )
                return
            self.load_preferences()
            self._initialized = True
            logger.info("SystemPromptManager initialized.")

    def shutdown(self) -> None:
        """Shut down the manager, persisting current preferences to disk.

        Calling this method when the manager is not initialized is a
        no-op.
        """
        with self._lock:
            if not self._initialized:
                logger.warning("SystemPromptManager.shutdown() called but not initialized.")
                return
            self.save_preferences()
            self._initialized = False
            logger.info("SystemPromptManager shut down.")

    # -------------------------------------------------------------------
    # Section registration
    # -------------------------------------------------------------------

    def register_section(self, section: PromptSection, *, overwrite: bool = False) -> None:
        """Register a new prompt section, or replace an existing one.

        This is the extension point that lets future developers add
        or change NOVA's behavior for a specific section without
        modifying this module.

        Args:
            section: The section to register.
            overwrite: If ``True``, replace an existing section
                registered under the same name.

        Raises:
            DuplicateSectionError: If a section is already registered
                under ``section.name`` and ``overwrite`` is ``False``.
        """
        with self._lock:
            self._builder.register_section(section, overwrite=overwrite)
            logger.info("Prompt section '%s' registered.", section.name)

    # -------------------------------------------------------------------
    # Profile management
    # -------------------------------------------------------------------

    def register_profile(self, profile: PromptProfile, *, overwrite: bool = False) -> None:
        """Register a new personality profile, or replace an existing one.

        Args:
            profile: The profile to register.
            overwrite: If ``True``, replace an existing profile
                registered under the same name.

        Raises:
            DuplicateProfileError: If a profile is already registered
                under ``profile.name`` and ``overwrite`` is ``False``.
        """
        with self._lock:
            if profile.name in self._profiles and not overwrite:
                raise DuplicateProfileError(
                    f"A prompt profile is already registered under the name "
                    f"'{profile.name}'."
                )
            self._profiles[profile.name] = profile
            logger.info("Prompt profile '%s' registered.", profile.name)

    def unregister_profile(self, name: str) -> None:
        """Remove a previously registered profile.

        Args:
            name: The unique name of the profile to remove.

        Raises:
            ProfileNotFoundError: If no profile is registered under
                ``name``.
        """
        with self._lock:
            if name not in self._profiles:
                raise ProfileNotFoundError(f"No prompt profile is registered under '{name}'.")
            del self._profiles[name]
            if self._active_profile_name == name:
                self._active_profile_name = ProfileName.DEFAULT.value
                logger.warning(
                    "Active profile '%s' was unregistered; falling back to 'default'.",
                    name,
                )
            logger.info("Prompt profile '%s' unregistered.", name)

    def profile_exists(self, name: str) -> bool:
        """Check whether a profile is currently registered under a name.

        Args:
            name: The unique name to check.

        Returns:
            ``True`` if a profile is registered under ``name``,
            ``False`` otherwise.
        """
        with self._lock:
            return name in self._profiles

    def list_profiles(self) -> tuple[str, ...]:
        """List the names of every currently registered profile.

        Returns:
            A tuple of registered profile names.
        """
        with self._lock:
            return tuple(self._profiles.keys())

    def get_profile(self, name: str) -> PromptProfile:
        """Retrieve a registered profile by name.

        Args:
            name: The unique name of the profile to retrieve.

        Returns:
            The registered :class:`PromptProfile`.

        Raises:
            ProfileNotFoundError: If no profile is registered under
                ``name``.
        """
        with self._lock:
            profile = self._profiles.get(name)
            if profile is None:
                raise ProfileNotFoundError(f"No prompt profile is registered under '{name}'.")
            return profile

    def set_active_profile(self, name: str) -> None:
        """Switch the manager's active personality profile.

        Args:
            name: The unique name of the profile to make active.

        Raises:
            ProfileNotFoundError: If no profile is registered under
                ``name``.
        """
        with self._lock:
            if name not in self._profiles:
                raise ProfileNotFoundError(f"No prompt profile is registered under '{name}'.")
            previous_name = self._active_profile_name
            self._active_profile_name = name
            logger.info("Active prompt profile switched from '%s' to '%s'.", previous_name, name)

    def get_active_profile(self) -> str:
        """Return the name of the currently active profile.

        Returns:
            The active profile's name.
        """
        with self._lock:
            return self._active_profile_name

    # -------------------------------------------------------------------
    # Prompt generation
    # -------------------------------------------------------------------

    def build_prompt(
        self,
        profile: ProfileName | str | None = None,
        context: PromptBuildContext | None = None,
    ) -> str:
        """Build the system prompt for a given profile and context.

        Args:
            profile: The profile to build the prompt with. If
                ``None``, the currently active profile (see
                :meth:`set_active_profile`) is used.
            context: Transient per-request context to inject. If
                ``None``, an empty :class:`PromptBuildContext` is used.

        Returns:
            The fully assembled system prompt text.

        Raises:
            SystemPromptError: If the manager is not initialized.
            ProfileNotFoundError: If ``profile`` does not refer to a
                registered profile.
        """
        with self._lock:
            self._ensure_initialized()
            resolved_profile_name = self._resolve_profile_name(profile)
            resolved_profile = self.get_profile(resolved_profile_name)
            resolved_context = context if context is not None else PromptBuildContext()
            preferences_snapshot = self._preferences

        section_text = self._builder.build(
            resolved_profile.section_names, preferences_snapshot, resolved_context
        )

        if resolved_profile.focus_instruction:
            prompt_text = f"{section_text}\n\n# Current Mode\n{resolved_profile.focus_instruction}"
        else:
            prompt_text = section_text

        logger.debug(
            "Built prompt using profile '%s' (%d sections).",
            resolved_profile_name,
            len(resolved_profile.section_names),
        )
        return prompt_text

    def preview_prompt(
        self,
        profile: ProfileName | str | None = None,
        context: PromptBuildContext | None = None,
        max_length: int = _DEFAULT_PREVIEW_LENGTH,
    ) -> str:
        """Build a truncated preview of a system prompt, for quick inspection.

        Args:
            profile: The profile to preview. If ``None``, the
                currently active profile is used.
            context: Transient per-request context to inject.
            max_length: The maximum number of characters to return
                before truncating with an ellipsis marker.

        Returns:
            The (possibly truncated) prompt text.

        Raises:
            SystemPromptError: If the manager is not initialized, or if
                ``max_length`` is not a positive integer.
            ProfileNotFoundError: If ``profile`` does not refer to a
                registered profile.
        """
        if not isinstance(max_length, int) or isinstance(max_length, bool) or max_length <= 0:
            raise SystemPromptError(f"max_length must be a positive integer, got {max_length!r}.")

        full_prompt = self.build_prompt(profile, context)
        if len(full_prompt) <= max_length:
            return full_prompt
        return f"{full_prompt[:max_length].rstrip()}...\n\n[truncated preview]"

    def export_prompt(
        self,
        export_path: Path,
        profile: ProfileName | str | None = None,
        context: PromptBuildContext | None = None,
    ) -> None:
        """Build a system prompt and write it to a plain text file.

        Args:
            export_path: The file to write the prompt text to.
            profile: The profile to build the prompt with. If
                ``None``, the currently active profile is used.
            context: Transient per-request context to inject.

        Raises:
            SystemPromptError: If the manager is not initialized, or if
                ``export_path`` cannot be written.
            ProfileNotFoundError: If ``profile`` does not refer to a
                registered profile.
        """
        prompt_text = self.build_prompt(profile, context)
        self._atomic_write_text(export_path, prompt_text)
        logger.info("Prompt exported to '%s'.", export_path)

    # -------------------------------------------------------------------
    # Preferences
    # -------------------------------------------------------------------

    def update_preferences(
        self,
        *,
        assistant_name: Any = _UNSET,
        user_title: Any = _UNSET,
        response_length: Any = _UNSET,
        humor_level: Any = _UNSET,
        emoji_usage: Any = _UNSET,
        verbosity: Any = _UNSET,
        coding_language: Any = _UNSET,
        formality: Any = _UNSET,
        greeting_style: Any = _UNSET,
        conversation_style: Any = _UNSET,
        custom_instructions: Any = _UNSET,
    ) -> NovaPreferences:
        """Update one or more preference fields and persist the result.

        Only fields explicitly provided are changed; any field left at
        its default is preserved unchanged.

        Args:
            assistant_name: The new assistant name, if changing it.
            user_title: The new user title, if changing it.
            response_length: The new response length preference, if
                changing it.
            humor_level: The new humor level, if changing it.
            emoji_usage: The new emoji usage preference, if changing
                it.
            verbosity: The new verbosity preference, if changing it.
            coding_language: The new preferred coding language, if
                changing it.
            formality: The new formality preference, if changing it.
            greeting_style: The new greeting style, if changing it.
            conversation_style: The new conversation style, if
                changing it.
            custom_instructions: The new custom instructions, if
                changing them.

        Returns:
            The updated :class:`NovaPreferences`.

        Raises:
            SystemPromptError: If the manager is not initialized, or if
                any provided field fails validation.
        """
        with self._lock:
            self._ensure_initialized()
            current = self._preferences

            updated = NovaPreferences(
                assistant_name=(
                    current.assistant_name
                    if assistant_name is _UNSET
                    else _validate_non_empty_string(assistant_name, "assistant_name")
                ),
                user_title=(
                    current.user_title
                    if user_title is _UNSET
                    else _validate_non_empty_string(user_title, "user_title")
                ),
                response_length=(
                    current.response_length
                    if response_length is _UNSET
                    else _coerce_enum(response_length, ResponseLength, "response_length")
                ),
                humor_level=(
                    current.humor_level
                    if humor_level is _UNSET
                    else _coerce_enum(humor_level, HumorLevel, "humor_level")
                ),
                emoji_usage=(
                    current.emoji_usage if emoji_usage is _UNSET else bool(emoji_usage)
                ),
                verbosity=(
                    current.verbosity
                    if verbosity is _UNSET
                    else _coerce_enum(verbosity, VerbosityLevel, "verbosity")
                ),
                coding_language=(
                    current.coding_language
                    if coding_language is _UNSET
                    else _validate_non_empty_string(coding_language, "coding_language")
                ),
                formality=(
                    current.formality
                    if formality is _UNSET
                    else _coerce_enum(formality, FormalityLevel, "formality")
                ),
                greeting_style=(
                    current.greeting_style
                    if greeting_style is _UNSET
                    else _coerce_enum(greeting_style, GreetingStyle, "greeting_style")
                ),
                conversation_style=(
                    current.conversation_style
                    if conversation_style is _UNSET
                    else _coerce_enum(conversation_style, ConversationStyle, "conversation_style")
                ),
                custom_instructions=(
                    current.custom_instructions
                    if custom_instructions is _UNSET
                    else _validate_custom_instructions(custom_instructions)
                ),
                updated_at=datetime.now(UTC),
            )

            self._preferences = updated
            self.save_preferences()
            logger.info("Preferences updated and saved.")
            return updated

    def load_preferences(self) -> NovaPreferences:
        """Load preferences from disk, recovering from corruption if necessary.

        If the storage file does not exist, default preferences are
        created and immediately persisted. If the storage file exists
        but cannot be parsed, it is quarantined (renamed aside with a
        timestamp) and default preferences are used instead.

        Returns:
            The loaded (or newly created default) :class:`NovaPreferences`.
        """
        with self._lock:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)

            if not self._storage_path.exists():
                logger.info(
                    "No existing preferences file found at '%s'; creating defaults.",
                    self._storage_path,
                )
                self._preferences = NovaPreferences()
                self.save_preferences()
                return self._preferences

            try:
                raw_text = self._storage_path.read_text(encoding="utf-8")
                payload = json.loads(raw_text)
                self._preferences = NovaPreferences.from_dict(payload)
            except (OSError, json.JSONDecodeError, SystemPromptError) as exc:
                logger.error(
                    "Preferences file at '%s' is corrupted or unreadable: %s. "
                    "Recovering with defaults.",
                    self._storage_path,
                    exc,
                    exc_info=True,
                )
                self._quarantine_corrupted_preferences()
                self._preferences = NovaPreferences()
                self.save_preferences()
                return self._preferences

            logger.info("Preferences loaded from '%s'.", self._storage_path)
            return self._preferences

    def save_preferences(self) -> None:
        """Persist the current preferences to disk atomically.

        Raises:
            SystemPromptError: If the preferences file cannot be
                written.
        """
        with self._lock:
            self._atomic_write_json(self._storage_path, self._preferences.to_dict())
            logger.debug("Preferences saved to '%s'.", self._storage_path)

    def reset_preferences(self) -> NovaPreferences:
        """Reset preferences to their default values and persist the result.

        Returns:
            The newly reset :class:`NovaPreferences`.

        Raises:
            SystemPromptError: If the manager is not initialized.
        """
        with self._lock:
            self._ensure_initialized()
            self._preferences = NovaPreferences()
            self.save_preferences()
            logger.warning("Preferences reset to defaults.")
            return self._preferences

    # -------------------------------------------------------------------
    # Diagnostics
    # -------------------------------------------------------------------

    def statistics(self) -> dict[str, object]:
        """Return summary statistics about the manager's current state.

        Returns:
            A dictionary describing the current preferences, the
            active profile, the number of registered profiles, the
            storage path, and the storage file's size in bytes.
        """
        with self._lock:
            preferences = self._preferences
            storage_size_bytes = (
                self._storage_path.stat().st_size if self._storage_path.exists() else 0
            )
            return {
                "assistant_name": preferences.assistant_name,
                "user_title": preferences.user_title,
                "response_length": preferences.response_length.value,
                "humor_level": preferences.humor_level.value,
                "formality": preferences.formality.value,
                "custom_instruction_count": len(preferences.custom_instructions),
                "active_profile": self._active_profile_name,
                "registered_profile_count": len(self._profiles),
                "storage_path": str(self._storage_path),
                "storage_size_bytes": storage_size_bytes,
                "initialized": self._initialized,
            }

    def health_check(self) -> bool:
        """Verify that the manager is initialized and its storage is writable.

        Returns:
            ``True`` if the manager is healthy, ``False`` otherwise.
        """
        with self._lock:
            if not self._initialized:
                logger.warning("Health check failed: SystemPromptManager is not initialized.")
                return False

            probe_path = self._storage_path.parent / f".health_check_{os.getpid()}.tmp"
            try:
                self._storage_path.parent.mkdir(parents=True, exist_ok=True)
                probe_path.write_text("ok", encoding="utf-8")
                probe_path.unlink()
            except OSError as exc:
                logger.error(
                    "Health check failed: preferences directory is not writable: %s",
                    exc,
                    exc_info=True,
                )
                return False

            logger.debug("SystemPromptManager health check passed.")
            return True

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    def _ensure_initialized(self) -> None:
        """Verify the manager is initialized before permitting an operation.

        Raises:
            SystemPromptError: If :meth:`initialize` has not been
                called successfully.
        """
        if not self._initialized:
            raise SystemPromptError(
                "SystemPromptManager is not initialized. Call initialize() first."
            )

    def _resolve_profile_name(self, profile: ProfileName | str | None) -> str:
        """Resolve a profile argument into a concrete registered profile name.

        Args:
            profile: A :class:`ProfileName` member, its string value,
                or ``None`` to use the active profile.

        Returns:
            The resolved profile name.
        """
        if profile is None:
            return self._active_profile_name
        if isinstance(profile, ProfileName):
            return profile.value
        return str(profile)

    def _quarantine_corrupted_preferences(self) -> None:
        """Rename a corrupted preferences file aside so it is not lost or reused."""
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        quarantine_path = self._storage_path.with_name(
            f"{self._storage_path.stem}.corrupted-{timestamp}{self._storage_path.suffix}"
        )
        try:
            self._storage_path.rename(quarantine_path)
            logger.warning("Corrupted preferences file quarantined at '%s'.", quarantine_path)
        except OSError as exc:
            logger.error(
                "Failed to quarantine corrupted preferences file at '%s': %s",
                self._storage_path,
                exc,
                exc_info=True,
            )

    @staticmethod
    def _atomic_write_json(target_path: Path, payload: dict[str, Any]) -> None:
        """Write a JSON payload to a file atomically.

        Args:
            target_path: The file to write the payload to.
            payload: The JSON-serializable payload to write.

        Raises:
            SystemPromptError: If the file cannot be written or moved
                into place.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target_path.parent,
                prefix=f".{target_path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                json.dump(payload, temp_file, indent=2, ensure_ascii=False)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)
            temp_path.replace(target_path)
        except OSError as exc:
            raise SystemPromptError(
                f"Failed to write preferences to '{target_path}': {exc}",
                original_exception=exc,
            ) from exc

    @staticmethod
    def _atomic_write_text(target_path: Path, text: str) -> None:
        """Write plain text to a file atomically.

        Args:
            target_path: The file to write the text to.
            text: The text to write.

        Raises:
            SystemPromptError: If the file cannot be written or moved
                into place.
        """
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=target_path.parent,
                prefix=f".{target_path.stem}.",
                suffix=".tmp",
                delete=False,
            ) as temp_file:
                temp_file.write(text)
                temp_file.flush()
                os.fsync(temp_file.fileno())
                temp_path = Path(temp_file.name)
            temp_path.replace(target_path)
        except OSError as exc:
            raise SystemPromptError(
                f"Failed to write prompt export to '{target_path}': {exc}",
                original_exception=exc,
            ) from exc


__all__ = [
    "SystemPromptManager",
    "PromptBuilder",
    "PromptProfile",
    "PromptSection",
    "PromptBuildContext",
    "NovaPreferences",
    "SectionRenderer",
    "SystemPromptError",
    "ProfileNotFoundError",
    "DuplicateProfileError",
    "SectionNotFoundError",
    "DuplicateSectionError",
    "ProfileName",
    "LanguageMode",
    "ResponseLength",
    "HumorLevel",
    "VerbosityLevel",
    "FormalityLevel",
    "GreetingStyle",
    "ConversationStyle",
]
