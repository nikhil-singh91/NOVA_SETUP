"""Deterministic emotion and conversation analysis for NOVA.

This module implements :class:`EmotionEngine`, a rule-based text
analyzer that infers the user's likely emotional state, the kind of
conversation currently taking place, and how NOVA should respond,
using only configurable keyword sets and simple, composable scoring
rules. It never calls an AI model, never depends on
:class:`~providers.provider_manager.ProviderManager`, and never
depends on :class:`~memory.memory_manager.MemoryManager`. It is a
pure, deterministic function of the text it is given.

Design:
    Detection is driven by scoring: each candidate label (an emotion
    or a conversation mode) accumulates a numeric score from one or
    more independent :data:`ScoringRule` callables. The default rule
    for both emotions and modes is a live keyword lookup against a
    mutable registry, so registering a new keyword takes effect
    immediately without rebuilding anything. A second default rule
    adds a small punctuation-based intensity signal for high-arousal
    emotions. Neither rule uses a hardcoded if/else chain; both are
    plain data-driven lookups.

Extensibility:
    New keyword-backed labels can be registered at any time via
    :meth:`EmotionEngine.register_emotion_keywords` and
    :meth:`EmotionEngine.register_mode_keywords`, and entirely new
    kinds of signals can be added via
    :meth:`EmotionEngine.register_emotion_scoring_rule` and
    :meth:`EmotionEngine.register_mode_scoring_rule`. This is how
    NOVA supports custom emotions and conversation modes beyond the
    built-in :class:`Emotion` and :class:`ConversationMode` enums,
    without modifying this file.

Consumption:
    :meth:`EmotionEngine.analyze_text` returns a single
    :class:`ConversationAnalysis`, a plain, structured dataclass with
    no dependency on any other NOVA subsystem. A caller such as
    ``SystemPromptManager`` (or whatever orchestrates it) reads the
    fields it needs — for example, ``analysis.emotion_description`` is
    ready to drop directly into a prompt context's emotion field.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Final, Mapping, Sequence

from core.exceptions import NovaError
from core.logger import get_logger

logger = get_logger(__name__)


class EmotionEngineError(NovaError):
    """Raised when NOVA's emotion analysis engine encounters an error."""

    default_message: str = "The emotion analysis engine encountered an error."


# =============================================================================
# Enums
# =============================================================================


class Emotion(str, Enum):
    """The built-in emotional states NOVA can detect.

    Attributes:
        HAPPY: The user appears pleased or content.
        SAD: The user appears down or unhappy.
        EXCITED: The user appears enthusiastic or thrilled.
        FRUSTRATED: The user appears stuck or annoyed by a problem.
        ANGRY: The user appears upset or irritated.
        CONFUSED: The user appears uncertain or lost.
        STRESSED: The user appears under pressure or overwhelmed.
        NERVOUS: The user appears anxious or apprehensive.
        MOTIVATED: The user appears driven and ready to act.
        TIRED: The user appears fatigued or low on energy.
        CALM: The user appears relaxed and even-tempered.
        NEUTRAL: No particular emotional signal was detected.
    """

    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    FRUSTRATED = "frustrated"
    ANGRY = "angry"
    CONFUSED = "confused"
    STRESSED = "stressed"
    NERVOUS = "nervous"
    MOTIVATED = "motivated"
    TIRED = "tired"
    CALM = "calm"
    NEUTRAL = "neutral"


class ConversationMode(str, Enum):
    """The built-in kinds of conversation NOVA can detect.

    Attributes:
        FRIEND: Personal, relationship-focused conversation.
        CODING: General software development assistance.
        DEBUGGING: Diagnosing and fixing a specific problem.
        STUDY: Learning a new concept step by step.
        DSA: Data structures, algorithms, or competitive programming.
        INTERVIEW: Mock technical interview practice.
        MOTIVATION: The user needs encouragement or a push forward.
        CASUAL: Low-stakes, relaxed conversation.
        PLANNING: Organizing tasks, schedules, or goals.
        GENERAL: No specific mode was detected; the default fallback.
    """

    FRIEND = "friend"
    CODING = "coding"
    DEBUGGING = "debugging"
    STUDY = "study"
    DSA = "dsa"
    INTERVIEW = "interview"
    MOTIVATION = "motivation"
    CASUAL = "casual"
    PLANNING = "planning"
    GENERAL = "general"


class ResponseTone(str, Enum):
    """The tones NOVA can be recommended to respond with.

    Attributes:
        FRIENDLY: Warm and approachable.
        SERIOUS: Focused and measured.
        ENCOURAGING: Supportive and reassuring.
        TEACHING: Patient and explanatory.
        PROFESSIONAL: Businesslike and efficient.
        HUMOROUS: Light and playful.
    """

    FRIENDLY = "friendly"
    SERIOUS = "serious"
    ENCOURAGING = "encouraging"
    TEACHING = "teaching"
    PROFESSIONAL = "professional"
    HUMOROUS = "humorous"


# =============================================================================
# Data model
# =============================================================================


@dataclass(frozen=True)
class KeywordRule:
    """A single weighted keyword or phrase used for scoring.

    Attributes:
        keyword: The keyword or phrase to search for, matched
            case-insensitively as a substring of the analyzed text.
        weight: The score contributed each time ``keyword`` is found.
            Higher weights represent stronger indicators.
    """

    keyword: str
    weight: float = 1.0


#: The signature every scoring rule must implement. A scoring rule
#: receives the raw analyzed text and returns a mapping of label to
#: the score it contributes for that label. Multiple rules may
#: contribute to the same label; their contributions are summed.
ScoringRule = Callable[[str], Mapping[str, float]]


@dataclass(frozen=True)
class ConversationAnalysis:
    """The structured result of analyzing a piece of user text.

    This is the primary object other NOVA subsystems consume. It has
    no dependency on any other module; every field is a plain enum,
    string, float, or mapping.

    Attributes:
        text_length: The character length of the analyzed text.
        detected_emotion: The best-matching built-in :class:`Emotion`.
        emotion_confidence: A confidence score in ``[0.0, 1.0]`` for
            ``detected_emotion``.
        emotion_scores: The full breakdown of scores for every label
            (built-in and custom) that scored above zero.
        detected_mode: The best-matching built-in
            :class:`ConversationMode`.
        mode_confidence: A confidence score in ``[0.0, 1.0]`` for
            ``detected_mode``.
        mode_scores: The full breakdown of scores for every mode label
            (built-in and custom) that scored above zero.
        recommended_tone: The :class:`ResponseTone` recommended given
            ``detected_emotion`` and ``detected_mode``.
        use_humor: Whether humor is contextually appropriate given
            ``detected_emotion`` and ``detected_mode``. This reflects
            context only; a caller should still combine it with the
            user's own humor preference.
        analyzed_at: The UTC timestamp at which this analysis was
            produced.
    """

    text_length: int
    detected_emotion: Emotion
    emotion_confidence: float
    emotion_scores: Mapping[str, float]
    detected_mode: ConversationMode
    mode_confidence: float
    mode_scores: Mapping[str, float]
    recommended_tone: ResponseTone
    use_humor: bool
    analyzed_at: datetime

    @property
    def emotion_description(self) -> str:
        """A short, human-readable description of the detected emotion.

        Suitable for use directly as a prompt context's emotion field.

        Returns:
            A description such as ``"frustrated (moderate confidence)"``.
        """
        return (
            f"{self.detected_emotion.value} "
            f"({_confidence_label(self.emotion_confidence)} confidence)"
        )


def _confidence_label(score: float) -> str:
    """Bucket a numeric confidence score into a human-readable label.

    Args:
        score: A confidence score in ``[0.0, 1.0]``.

    Returns:
        ``"low"``, ``"moderate"``, or ``"high"``.
    """
    if score >= 0.66:
        return "high"
    if score >= 0.33:
        return "moderate"
    return "low"


def _validate_label(label: str) -> str:
    """Validate and normalize a registration label.

    Args:
        label: The label to validate.

    Returns:
        The stripped, lowercased label.

    Raises:
        EmotionEngineError: If ``label`` is not a non-empty string.
    """
    if not isinstance(label, str) or not label.strip():
        raise EmotionEngineError("A registration label must be a non-empty string.")
    return label.strip().lower()


def _validate_keyword_rules(rules: Sequence[KeywordRule]) -> tuple[KeywordRule, ...]:
    """Validate a sequence of keyword rules.

    Args:
        rules: The rules to validate.

    Returns:
        The validated rules, as an immutable tuple.

    Raises:
        EmotionEngineError: If ``rules`` is empty, if any rule's
            keyword is not a non-empty string, or if any rule's
            weight is not a positive number.
    """
    if not rules:
        raise EmotionEngineError("At least one keyword rule must be provided.")

    for rule in rules:
        if not isinstance(rule.keyword, str) or not rule.keyword.strip():
            raise EmotionEngineError("Every keyword rule must have a non-empty keyword.")
        if not isinstance(rule.weight, (int, float)) or isinstance(rule.weight, bool) or rule.weight <= 0:
            raise EmotionEngineError(
                f"Keyword rule weight must be a positive number, got {rule.weight!r}."
            )
    return tuple(rules)


def _validate_text(text: str) -> str:
    """Validate that a value is analyzable text.

    Args:
        text: The value to validate.

    Returns:
        The original text, unchanged.

    Raises:
        EmotionEngineError: If ``text`` is not a string, or is empty.
    """
    if not isinstance(text, str) or not text.strip():
        raise EmotionEngineError("Text to analyze must be a non-empty string.")
    return text


# =============================================================================
# Built-in scoring rules
# =============================================================================


class _KeywordScorer:
    """A scoring rule that scores text against a live keyword registry.

    Because this class holds a reference to the registry dictionary
    itself, rather than a snapshot of it, registering a new label's
    keywords after construction takes effect immediately for every
    subsequent call.

    Attributes:
        _registry: The mutable mapping of label to the keyword rules
            that score it.
    """

    def __init__(self, registry: dict[str, tuple[KeywordRule, ...]]) -> None:
        """Initialize the scorer with a reference to a keyword registry.

        Args:
            registry: The mutable keyword registry to score against.
        """
        self._registry = registry

    def __call__(self, text: str) -> dict[str, float]:
        """Score text against every label in the registry.

        Args:
            text: The text to score.

        Returns:
            A mapping of label to the total score contributed by
            keyword matches, omitting labels that scored zero.
        """
        lowered_text = text.lower()
        scores: dict[str, float] = {}
        for label, rules in self._registry.items():
            label_score = 0.0
            for rule in rules:
                occurrences = lowered_text.count(rule.keyword.lower())
                if occurrences:
                    label_score += occurrences * rule.weight
            if label_score > 0:
                scores[label] = label_score
        return scores


class _PunctuationIntensityScorer:
    """A scoring rule that adds an intensity bonus for high-arousal emotions.

    Exclamation marks and fully capitalized words are treated as
    signals of heightened intensity, and contribute a small, evenly
    split bonus toward the emotions most associated with elevated
    arousal: excitement, anger, and frustration. This does not
    determine which of the three is correct; keyword scoring and
    other rules remain responsible for that distinction. It only
    boosts their combined likelihood relative to low-arousal emotions.

    Attributes:
        _target_labels: The emotion labels this rule contributes to.
        _weight_per_signal: The score contributed per detected signal.
    """

    _WORD_PATTERN: Final[re.Pattern[str]] = re.compile(r"[A-Za-z']+")

    def __init__(
        self,
        target_labels: tuple[str, ...] = (Emotion.EXCITED.value, Emotion.ANGRY.value, Emotion.FRUSTRATED.value),
        weight_per_signal: float = 0.5,
    ) -> None:
        """Initialize the intensity scorer.

        Args:
            target_labels: The emotion labels to distribute the
                intensity bonus across.
            weight_per_signal: The score contributed per exclamation
                mark or fully capitalized word detected.
        """
        self._target_labels = target_labels
        self._weight_per_signal = weight_per_signal

    def __call__(self, text: str) -> dict[str, float]:
        """Score text based on punctuation and capitalization intensity.

        Args:
            text: The text to score.

        Returns:
            A mapping of each target label to its share of the total
            intensity bonus, or an empty mapping if no intensity
            signals were found.
        """
        exclamation_count = text.count("!")
        words = self._WORD_PATTERN.findall(text)
        shouted_word_count = sum(1 for word in words if len(word) > 2 and word.isupper())

        total_intensity = (exclamation_count + shouted_word_count) * self._weight_per_signal
        if total_intensity <= 0 or not self._target_labels:
            return {}

        share = total_intensity / len(self._target_labels)
        return {label: share for label in self._target_labels}


# =============================================================================
# Default keyword registries
# =============================================================================


def _default_emotion_keywords() -> dict[str, tuple[KeywordRule, ...]]:
    """Build the default keyword registry for built-in emotions.

    Returns:
        A mapping of emotion label to its default keyword rules.
    """
    return {
        Emotion.HAPPY.value: (
            KeywordRule("happy", 1.0),
            KeywordRule("glad", 1.0),
            KeywordRule("great news", 1.2),
            KeywordRule("awesome", 1.0),
            KeywordRule("wonderful", 1.0),
            KeywordRule("yay", 1.0),
            KeywordRule("khush", 1.0),
            KeywordRule("mast", 0.8),
        ),
        Emotion.SAD.value: (
            KeywordRule("sad", 1.2),
            KeywordRule("down", 0.8),
            KeywordRule("depressed", 1.5),
            KeywordRule("unhappy", 1.0),
            KeywordRule("heartbroken", 1.5),
            KeywordRule("miss", 0.6),
            KeywordRule("upset", 1.0),
        ),
        Emotion.EXCITED.value: (
            KeywordRule("excited", 1.5),
            KeywordRule("can't wait", 1.2),
            KeywordRule("pumped", 1.2),
            KeywordRule("thrilled", 1.2),
            KeywordRule("let's go", 0.8),
            KeywordRule("finally", 0.5),
            KeywordRule("finally solved", 1.5),
            KeywordRule("it worked", 1.4),
            KeywordRule("solved that bug", 1.5),
            KeywordRule("got selected", 1.5),
        ),
        Emotion.FRUSTRATED.value: (
            KeywordRule("frustrated", 1.5),
            KeywordRule("annoying", 1.0),
            KeywordRule("stuck", 1.0),
            KeywordRule("why isn't this working", 1.3),
            KeywordRule("this isn't working", 1.0),
            KeywordRule("ugh", 0.8),
            KeywordRule("bakwas", 1.0),
            KeywordRule("dimaag kharab", 1.5),
            KeywordRule("driving me crazy", 1.5),
            KeywordRule("three hours", 1.0),
        ),
        Emotion.ANGRY.value: (
            KeywordRule("angry", 1.5),
            KeywordRule("furious", 1.5),
            KeywordRule("pissed off", 1.4),
            KeywordRule("hate this", 1.2),
            KeywordRule("so annoyed", 1.1),
        ),
        Emotion.CONFUSED.value: (
            KeywordRule("confused", 1.5),
            KeywordRule("don't understand", 1.3),
            KeywordRule("not sure what", 1.0),
            KeywordRule("makes no sense", 1.2),
            KeywordRule("lost", 0.8),
            KeywordRule("what does this mean", 1.0),
        ),
        Emotion.STRESSED.value: (
            KeywordRule("stressed", 1.5),
            KeywordRule("overwhelmed", 1.4),
            KeywordRule("too much", 0.8),
            KeywordRule("deadline", 0.6),
            KeywordRule("under pressure", 1.2),
            KeywordRule("can't keep up", 1.2),
        ),
        Emotion.NERVOUS.value: (
            KeywordRule("nervous", 1.5),
            KeywordRule("anxious", 1.4),
            KeywordRule("worried", 1.2),
            KeywordRule("scared", 1.0),
            KeywordRule("what if i fail", 1.3),
        ),
        Emotion.MOTIVATED.value: (
            KeywordRule("motivated", 1.5),
            KeywordRule("ready to", 0.8),
            KeywordRule("let's do this", 1.2),
            KeywordRule("determined", 1.2),
            KeywordRule("focused", 0.6),
        ),
        Emotion.TIRED.value: (
            KeywordRule("tired", 1.5),
            KeywordRule("exhausted", 1.4),
            KeywordRule("exhausting", 1.4),
            KeywordRule("sleepy", 1.0),
            KeywordRule("no energy", 1.2),
            KeywordRule("thak gaya", 1.0),
            KeywordRule("pura din", 1.2),
            KeywordRule("drained", 1.3),
            KeywordRule("long day", 1.2),
            KeywordRule("rough day", 1.2),
        ),
        Emotion.CALM.value: (
            KeywordRule("calm", 1.3),
            KeywordRule("relaxed", 1.2),
            KeywordRule("chill", 1.0),
            KeywordRule("peaceful", 1.0),
            KeywordRule("at ease", 1.0),
        ),
    }


def _default_mode_keywords() -> dict[str, tuple[KeywordRule, ...]]:
    """Build the default keyword registry for built-in conversation modes.

    Returns:
        A mapping of conversation mode label to its default keyword
        rules.
    """
    return {
        ConversationMode.FRIEND.value: (
            KeywordRule("just wanted to talk", 1.3),
            KeywordRule("how are you", 1.0),
            KeywordRule("miss you", 1.2),
            KeywordRule("let's chat", 1.0),
            KeywordRule("dost", 0.8),
            KeywordRule("today was", 1.2),
            KeywordRule("exhausting", 1.2),
            KeywordRule("rough day", 1.2),
            KeywordRule("weird day", 1.2),
            KeywordRule("pura din", 1.2),
            KeywordRule("speak very less", 1.5),
            KeywordRule("why do you speak", 1.5),
        ),
        ConversationMode.CODING.value: (
            KeywordRule("write a function", 1.4),
            KeywordRule("implement", 1.1),
            KeywordRule("refactor", 1.2),
            KeywordRule("build a feature", 1.3),
            KeywordRule("class", 0.6),
            KeywordRule("api", 0.8),
            KeywordRule("python", 0.7),
            KeywordRule("javascript", 0.7),
        ),
        ConversationMode.DEBUGGING.value: (
            KeywordRule("error", 1.3),
            KeywordRule("exception", 1.3),
            KeywordRule("traceback", 1.5),
            KeywordRule("stack trace", 1.5),
            KeywordRule("not working", 1.2),
            KeywordRule("crashes", 1.2),
            KeywordRule("bug", 1.2),
            KeywordRule("broken", 1.0),
        ),
        ConversationMode.STUDY.value: (
            KeywordRule("explain", 1.2),
            KeywordRule("teach me", 1.4),
            KeywordRule("how does", 0.9),
            KeywordRule("what is", 0.6),
            KeywordRule("i want to learn", 1.3),
            KeywordRule("understand", 0.7),
        ),
        ConversationMode.DSA.value: (
            KeywordRule("leetcode", 1.5),
            KeywordRule("time complexity", 1.5),
            KeywordRule("big o", 1.4),
            KeywordRule("data structure", 1.3),
            KeywordRule("binary search", 1.2),
            KeywordRule("dynamic programming", 1.4),
            KeywordRule("competitive programming", 1.4),
        ),
        ConversationMode.INTERVIEW.value: (
            KeywordRule("mock interview", 1.6),
            KeywordRule("technical interview", 1.5),
            KeywordRule("interview question", 1.3),
            KeywordRule("whiteboard", 1.1),
            KeywordRule("hiring", 0.7),
        ),
        ConversationMode.MOTIVATION.value: (
            KeywordRule("motivate me", 1.6),
            KeywordRule("feeling demotivated", 1.5),
            KeywordRule("want to give up", 1.5),
            KeywordRule("can't do this", 1.2),
            KeywordRule("inspire me", 1.3),
            KeywordRule("procrastinating", 1.1),
        ),
        ConversationMode.CASUAL.value: (
            KeywordRule("lol", 0.9),
            KeywordRule("haha", 0.8),
            KeywordRule("just chilling", 1.2),
            KeywordRule("bored", 0.8),
            KeywordRule("what's up", 0.8),
        ),
        ConversationMode.PLANNING.value: (
            KeywordRule("let's plan", 1.4),
            KeywordRule("schedule", 1.1),
            KeywordRule("roadmap", 1.2),
            KeywordRule("organize", 1.0),
            KeywordRule("todo list", 1.2),
            KeywordRule("timeline", 1.0),
        ),
    }


# =============================================================================
# Recommendation tables
# =============================================================================

_MODE_TONE_DEFAULTS: Final[dict[ConversationMode, ResponseTone]] = {
    ConversationMode.FRIEND: ResponseTone.FRIENDLY,
    ConversationMode.CODING: ResponseTone.TEACHING,
    ConversationMode.DEBUGGING: ResponseTone.SERIOUS,
    ConversationMode.STUDY: ResponseTone.TEACHING,
    ConversationMode.DSA: ResponseTone.TEACHING,
    ConversationMode.INTERVIEW: ResponseTone.PROFESSIONAL,
    ConversationMode.MOTIVATION: ResponseTone.ENCOURAGING,
    ConversationMode.CASUAL: ResponseTone.HUMOROUS,
    ConversationMode.PLANNING: ResponseTone.PROFESSIONAL,
    ConversationMode.GENERAL: ResponseTone.FRIENDLY,
}

_EMOTION_TONE_OVERRIDES: Final[dict[Emotion, ResponseTone]] = {
    Emotion.FRUSTRATED: ResponseTone.ENCOURAGING,
    Emotion.ANGRY: ResponseTone.SERIOUS,
    Emotion.CONFUSED: ResponseTone.TEACHING,
    Emotion.STRESSED: ResponseTone.ENCOURAGING,
    Emotion.NERVOUS: ResponseTone.ENCOURAGING,
    Emotion.SAD: ResponseTone.ENCOURAGING,
    Emotion.TIRED: ResponseTone.ENCOURAGING,
}

_HUMOR_DISALLOWED_EMOTIONS: Final[frozenset[Emotion]] = frozenset(
    {Emotion.SAD, Emotion.ANGRY, Emotion.FRUSTRATED, Emotion.STRESSED, Emotion.NERVOUS}
)

_HUMOR_DISALLOWED_MODES: Final[frozenset[ConversationMode]] = frozenset(
    {ConversationMode.DEBUGGING, ConversationMode.INTERVIEW, ConversationMode.PLANNING}
)


def confidence_score(scores: Mapping[str, float]) -> float:
    """Compute a normalized confidence score for a set of label scores.

    Confidence is expressed as the winning label's share of the total
    score across all candidates: a label that dominates the field
    yields a confidence near ``1.0``, while several labels scoring
    similarly yield a lower confidence, reflecting genuine ambiguity.

    Args:
        scores: A mapping of label to non-negative score.

    Returns:
        A confidence value in ``[0.0, 1.0]``. Returns ``0.0`` if
        ``scores`` is empty or every score is zero.
    """
    if not scores:
        return 0.0

    total = sum(max(0.0, value) for value in scores.values())
    if total <= 0:
        return 0.0

    top_score = max(scores.values())
    return min(1.0, top_score / total)


# =============================================================================
# Emotion engine
# =============================================================================


class EmotionEngine:
    """NOVA's deterministic emotion and conversation analysis engine.

    ``EmotionEngine`` scores user text against configurable keyword
    registries and composable scoring rules to infer an emotional
    state, a conversation mode, a recommended response tone, and
    whether humor is contextually appropriate. It performs no network
    calls, no model inference, and no I/O; every method is a pure
    function of its inputs and the engine's current registries.

    Attributes:
        _lock: A reentrant lock guarding the mutable keyword
            registries and rule lists, making registration and
            analysis thread-safe.
        _emotion_keywords: The mutable keyword registry for emotions.
        _mode_keywords: The mutable keyword registry for conversation
            modes.
        _emotion_rules: The ordered list of scoring rules applied when
            scoring emotions.
        _mode_rules: The ordered list of scoring rules applied when
            scoring conversation modes.
    """

    def __init__(self) -> None:
        """Construct an emotion engine seeded with NOVA's default rules."""
        self._lock: threading.RLock = threading.RLock()
        self._emotion_keywords: dict[str, tuple[KeywordRule, ...]] = _default_emotion_keywords()
        self._mode_keywords: dict[str, tuple[KeywordRule, ...]] = _default_mode_keywords()

        self._emotion_rules: list[ScoringRule] = [
            _KeywordScorer(self._emotion_keywords),
            _PunctuationIntensityScorer(),
        ]
        self._mode_rules: list[ScoringRule] = [
            _KeywordScorer(self._mode_keywords),
        ]

    # -------------------------------------------------------------------
    # Registration
    # -------------------------------------------------------------------

    def register_emotion_keywords(
        self, label: str, rules: Sequence[KeywordRule], *, overwrite: bool = False
    ) -> None:
        """Register keyword rules for an emotion label.

        The label may be one of the built-in :class:`Emotion` values,
        or an entirely new, custom label. Custom labels immediately
        become visible through :meth:`score_emotions` and
        :meth:`detect_emotion_label`, though :meth:`detect_emotion`
        remains restricted to the built-in :class:`Emotion` enum.

        Args:
            label: The emotion label to register keywords for.
            rules: The keyword rules that score this label.
            overwrite: If ``True``, replace any existing keyword rules
                already registered for ``label``.

        Raises:
            EmotionEngineError: If ``label`` is invalid, if ``rules``
                is empty or contains an invalid rule, or if
                ``overwrite`` is ``False`` and ``label`` is already
                registered.
        """
        with self._lock:
            normalized_label = _validate_label(label)
            validated_rules = _validate_keyword_rules(rules)

            if normalized_label in self._emotion_keywords and not overwrite:
                raise EmotionEngineError(
                    f"Emotion keywords are already registered for label "
                    f"'{normalized_label}'."
                )

            self._emotion_keywords[normalized_label] = validated_rules
            logger.info(
                "Registered %d keyword rule(s) for emotion label '%s'.",
                len(validated_rules),
                normalized_label,
            )

    def register_mode_keywords(
        self, label: str, rules: Sequence[KeywordRule], *, overwrite: bool = False
    ) -> None:
        """Register keyword rules for a conversation mode label.

        Args:
            label: The conversation mode label to register keywords
                for.
            rules: The keyword rules that score this label.
            overwrite: If ``True``, replace any existing keyword rules
                already registered for ``label``.

        Raises:
            EmotionEngineError: If ``label`` is invalid, if ``rules``
                is empty or contains an invalid rule, or if
                ``overwrite`` is ``False`` and ``label`` is already
                registered.
        """
        with self._lock:
            normalized_label = _validate_label(label)
            validated_rules = _validate_keyword_rules(rules)

            if normalized_label in self._mode_keywords and not overwrite:
                raise EmotionEngineError(
                    f"Mode keywords are already registered for label "
                    f"'{normalized_label}'."
                )

            self._mode_keywords[normalized_label] = validated_rules
            logger.info(
                "Registered %d keyword rule(s) for conversation mode label '%s'.",
                len(validated_rules),
                normalized_label,
            )

    def register_emotion_scoring_rule(self, rule: ScoringRule) -> None:
        """Register an additional scoring rule for emotion detection.

        Use this to add an entirely new kind of signal (beyond
        keyword matching) that contributes to emotion scores.

        Args:
            rule: A callable matching the :data:`ScoringRule`
                signature.
        """
        with self._lock:
            self._emotion_rules.append(rule)
            logger.info("Registered a custom emotion scoring rule.")

    def register_mode_scoring_rule(self, rule: ScoringRule) -> None:
        """Register an additional scoring rule for conversation mode detection.

        Args:
            rule: A callable matching the :data:`ScoringRule`
                signature.
        """
        with self._lock:
            self._mode_rules.append(rule)
            logger.info("Registered a custom conversation mode scoring rule.")

    def list_registered_emotion_labels(self) -> tuple[str, ...]:
        """List every emotion label currently registered with keyword rules.

        Returns:
            A tuple of registered emotion labels, built-in and custom.
        """
        with self._lock:
            return tuple(self._emotion_keywords.keys())

    def list_registered_mode_labels(self) -> tuple[str, ...]:
        """List every conversation mode label currently registered with keyword rules.

        Returns:
            A tuple of registered conversation mode labels, built-in
            and custom.
        """
        with self._lock:
            return tuple(self._mode_keywords.keys())

    # -------------------------------------------------------------------
    # Scoring
    # -------------------------------------------------------------------

    def score_emotions(self, text: str) -> dict[str, float]:
        """Score text against every registered emotion label.

        Args:
            text: The text to score.

        Returns:
            A mapping of emotion label to its total score, including
            any custom labels registered via
            :meth:`register_emotion_keywords`. Labels with a score of
            zero are omitted.

        Raises:
            EmotionEngineError: If ``text`` is not a non-empty string.
        """
        validated_text = _validate_text(text)
        with self._lock:
            rules = tuple(self._emotion_rules)

        combined_scores: dict[str, float] = {}
        for rule in rules:
            for label, score in rule(validated_text).items():
                combined_scores[label] = combined_scores.get(label, 0.0) + score
        return combined_scores

    def score_conversation_modes(self, text: str) -> dict[str, float]:
        """Score text against every registered conversation mode label.

        Args:
            text: The text to score.

        Returns:
            A mapping of conversation mode label to its total score,
            including any custom labels registered via
            :meth:`register_mode_keywords`. Labels with a score of
            zero are omitted.

        Raises:
            EmotionEngineError: If ``text`` is not a non-empty string.
        """
        validated_text = _validate_text(text)
        with self._lock:
            rules = tuple(self._mode_rules)

        combined_scores: dict[str, float] = {}
        for rule in rules:
            for label, score in rule(validated_text).items():
                combined_scores[label] = combined_scores.get(label, 0.0) + score
        return combined_scores

    # -------------------------------------------------------------------
    # Detection
    # -------------------------------------------------------------------

    def detect_emotion(self, text: str) -> Emotion:
        """Detect the single best-matching built-in emotion for text.

        Custom emotion labels registered via
        :meth:`register_emotion_keywords` may score highly but are not
        eligible to be returned here; use :meth:`detect_emotion_label`
        to see the unrestricted top label.

        Args:
            text: The text to analyze.

        Returns:
            The highest-scoring built-in :class:`Emotion`, or
            :attr:`Emotion.NEUTRAL` if no built-in emotion scored
            above zero.

        Raises:
            EmotionEngineError: If ``text`` is not a non-empty string.
        """
        scores = self.score_emotions(text)
        return self._best_enum_match(scores, Emotion, Emotion.NEUTRAL)

    def detect_conversation_mode(self, text: str) -> ConversationMode:
        """Detect the single best-matching built-in conversation mode for text.

        Custom mode labels registered via :meth:`register_mode_keywords`
        may score highly but are not eligible to be returned here; use
        :meth:`detect_conversation_mode_label` to see the unrestricted
        top label.

        Args:
            text: The text to analyze.

        Returns:
            The highest-scoring built-in :class:`ConversationMode`, or
            :attr:`ConversationMode.GENERAL` if no built-in mode
            scored above zero.

        Raises:
            EmotionEngineError: If ``text`` is not a non-empty string.
        """
        scores = self.score_conversation_modes(text)
        return self._best_enum_match(scores, ConversationMode, ConversationMode.GENERAL)

    def detect_emotion_label(self, text: str) -> str:
        """Detect the single best-matching emotion label, built-in or custom.

        Args:
            text: The text to analyze.

        Returns:
            The highest-scoring emotion label, or
            :attr:`Emotion.NEUTRAL`'s value if no label scored above
            zero.

        Raises:
            EmotionEngineError: If ``text`` is not a non-empty string.
        """
        scores = self.score_emotions(text)
        if not scores:
            return Emotion.NEUTRAL.value
        return max(scores.items(), key=lambda item: item[1])[0]

    def detect_conversation_mode_label(self, text: str) -> str:
        """Detect the single best-matching conversation mode label, built-in or custom.

        Args:
            text: The text to analyze.

        Returns:
            The highest-scoring conversation mode label, or
            :attr:`ConversationMode.GENERAL`'s value if no label
            scored above zero.

        Raises:
            EmotionEngineError: If ``text`` is not a non-empty string.
        """
        scores = self.score_conversation_modes(text)
        if not scores:
            return ConversationMode.GENERAL.value
        return max(scores.items(), key=lambda item: item[1])[0]

    # -------------------------------------------------------------------
    # Recommendation
    # -------------------------------------------------------------------

    def recommend_tone(self, emotion: Emotion, mode: ConversationMode) -> ResponseTone:
        """Recommend a response tone for a given emotion and conversation mode.

        The recommendation starts from a per-mode default tone, then
        applies an emotion-specific override if the detected emotion
        is one that should take precedence over the mode's default
        (for example, frustration calls for an encouraging tone
        regardless of whether the mode is coding or studying).

        Args:
            emotion: The detected emotion.
            mode: The detected conversation mode.

        Returns:
            The recommended :class:`ResponseTone`.
        """
        if emotion in _EMOTION_TONE_OVERRIDES:
            return _EMOTION_TONE_OVERRIDES[emotion]
        return _MODE_TONE_DEFAULTS.get(mode, ResponseTone.FRIENDLY)

    def should_use_humor(self, emotion: Emotion, mode: ConversationMode) -> bool:
        """Determine whether humor is contextually appropriate.

        This reflects context only, based on the detected emotion and
        conversation mode. It does not account for the user's own
        humor preference; a caller should combine this with that
        preference (for example, never using humor if the user has
        disabled it, even when this method returns ``True``).

        Args:
            emotion: The detected emotion.
            mode: The detected conversation mode.

        Returns:
            ``False`` if ``emotion`` or ``mode`` is one where humor
            would be inappropriate, ``True`` otherwise.
        """
        if emotion in _HUMOR_DISALLOWED_EMOTIONS:
            return False
        if mode in _HUMOR_DISALLOWED_MODES:
            return False
        return True

    # -------------------------------------------------------------------
    # Combined analysis
    # -------------------------------------------------------------------

    def analyze_text(self, text: str) -> ConversationAnalysis:
        """Run full emotion and conversation analysis on a piece of text.

        Args:
            text: The text to analyze.

        Returns:
            A :class:`ConversationAnalysis` combining emotion
            detection, conversation mode detection, tone
            recommendation, and humor appropriateness.

        Raises:
            EmotionEngineError: If ``text`` is not a non-empty string.
        """
        validated_text = _validate_text(text)

        emotion_scores = self.score_emotions(validated_text)
        mode_scores = self.score_conversation_modes(validated_text)

        detected_emotion = self._best_enum_match(emotion_scores, Emotion, Emotion.NEUTRAL)
        detected_mode = self._best_enum_match(mode_scores, ConversationMode, ConversationMode.GENERAL)

        known_emotion_scores = self._filter_known_enum_scores(emotion_scores, Emotion)
        known_mode_scores = self._filter_known_enum_scores(mode_scores, ConversationMode)

        emotion_confidence = confidence_score(known_emotion_scores)
        mode_confidence = confidence_score(known_mode_scores)

        recommended_tone = self.recommend_tone(detected_emotion, detected_mode)
        use_humor = self.should_use_humor(detected_emotion, detected_mode)

        analysis = ConversationAnalysis(
            text_length=len(validated_text),
            detected_emotion=detected_emotion,
            emotion_confidence=emotion_confidence,
            emotion_scores=dict(emotion_scores),
            detected_mode=detected_mode,
            mode_confidence=mode_confidence,
            mode_scores=dict(mode_scores),
            recommended_tone=recommended_tone,
            use_humor=use_humor,
            analyzed_at=datetime.now(timezone.utc),
        )

        logger.debug(
            "Analyzed text (%d chars): emotion=%s (%.2f), mode=%s (%.2f), tone=%s, humor=%s.",
            analysis.text_length,
            detected_emotion.value,
            emotion_confidence,
            detected_mode.value,
            mode_confidence,
            recommended_tone.value,
            use_humor,
        )
        return analysis

    # -------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------

    @staticmethod
    def _filter_known_enum_scores(
        scores: Mapping[str, float], enum_cls: type[Enum]
    ) -> dict[str, float]:
        """Filter a score mapping down to labels matching a known enum.

        Args:
            scores: The full score mapping, possibly including custom
                labels.
            enum_cls: The enum class whose values are considered
                "known".

        Returns:
            A mapping containing only entries whose label matches a
            member value of ``enum_cls``.
        """
        known_values = {member.value for member in enum_cls}
        return {label: score for label, score in scores.items() if label in known_values}

    def health_check(self) -> bool:
        """Verify that the emotion engine is initialized and functional.

        Returns:
            ``True`` if the engine is healthy, ``False`` otherwise.
        """
        try:
            analysis = self.analyze_text("hello")
            return analysis is not None
        except Exception as exc:
            logger.debug("[emotion_engine] Health check failed: %s", exc)
            return False

    @classmethod
    def _best_enum_match(
        cls,
        scores: Mapping[str, float],
        enum_cls: type[Enum],
        default: Enum,
    ) -> Enum:
        """Select the highest-scoring label that matches a known enum member.

        Args:
            scores: The full score mapping, possibly including custom
                labels that do not belong to ``enum_cls``.
            enum_cls: The enum class to restrict the result to.
            default: The value to return if no label in ``scores``
                matches a member of ``enum_cls``.

        Returns:
            The best-matching enum member, or ``default``.
        """
        known_scores = cls._filter_known_enum_scores(scores, enum_cls)
        if not known_scores:
            return default

        best_label = max(known_scores.items(), key=lambda item: item[1])[0]
        return enum_cls(best_label)


__all__ = [
    "EmotionEngine",
    "EmotionEngineError",
    "Emotion",
    "ConversationMode",
    "ResponseTone",
    "KeywordRule",
    "ScoringRule",
    "ConversationAnalysis",
    "confidence_score",
]
