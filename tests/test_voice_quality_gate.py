"""Comprehensive tests for TranscriptQualityGate, acoustic validation, and false-trigger suppression."""

from __future__ import annotations

import math
import numpy as np
import pytest

from voice.commands import CommandRecognizer, VoiceCommandRouter
from voice.manager import VoiceManager
from voice.quality import TranscriptQualityGate
from voice.state import QualityDecision, TranscriptionResult, VoiceState


# ==============================================================================
# TEST 1: Rejection of Cough / Noise / High No-Speech Probability
# ==============================================================================

def test_quality_gate_rejects_high_no_speech_prob() -> None:
    """Test 1: Audio with high no_speech_prob (coughs, throat clearing, breathing) is rejected."""
    gate = TranscriptQualityGate()

    # Simulate cough that Whisper transcribed into hallucinated text with high no_speech_prob
    cough_res = TranscriptionResult(
        text="bye thank you",
        confidence=0.15,
        no_speech_prob=0.85,
        avg_logprob=-1.40,
        compression_ratio=1.1,
        speech_duration=0.45,
    )

    eval_result = gate.evaluate(cough_res)
    assert not eval_result.accepted
    assert eval_result.decision in (QualityDecision.REJECTED_NOISE, QualityDecision.REJECTED_HALLUCINATION)
    assert "non-speech" in eval_result.reason.lower() or "hallucination" in eval_result.reason.lower()
    assert not eval_result.is_command_candidate


# ==============================================================================
# TEST 2: Rejection of Whisper Hallucinations & Repetition Loops
# ==============================================================================

def test_quality_gate_rejects_hallucination_and_repetition() -> None:
    """Test 2: Repetitive loops and classic subtitle hallucinations are rejected."""
    gate = TranscriptQualityGate()

    # 1. High compression ratio repetition
    rep_res = TranscriptionResult(
        text="thank you thank you thank you thank you thank you",
        confidence=0.30,
        no_speech_prob=0.10,
        avg_logprob=-0.50,
        compression_ratio=3.2,
        speech_duration=1.2,
    )
    eval_rep = gate.evaluate(rep_res)
    assert not eval_rep.accepted
    assert eval_rep.decision == QualityDecision.REJECTED_HALLUCINATION

    # 2. Subtitle hallucination on brief non-speech sound
    sub_res = TranscriptionResult(
        text="Thanks for watching!",
        confidence=0.40,
        no_speech_prob=0.30,
        avg_logprob=-0.80,
        compression_ratio=1.0,
        speech_duration=0.5,
    )
    eval_sub = gate.evaluate(sub_res)
    assert not eval_sub.accepted
    assert eval_sub.decision == QualityDecision.REJECTED_HALLUCINATION


# ==============================================================================
# TEST 3: Rejection of Empty or Punctuation-Only Transcripts
# ==============================================================================

def test_quality_gate_rejects_empty_and_noise_symbols() -> None:
    """Test 3: Empty text or punctuation-only transcripts are rejected cleanly."""
    gate = TranscriptQualityGate()

    # Empty
    empty_res = TranscriptionResult(text="", confidence=0.0)
    assert gate.evaluate(empty_res).decision == QualityDecision.REJECTED_EMPTY

    # Punctuation only
    punct_res = TranscriptionResult(text="... -- !!", confidence=0.5)
    assert gate.evaluate(punct_res).decision == QualityDecision.REJECTED_NOISE


# ==============================================================================
# TEST 4: Acceptance of Natural Language Voice Commands
# ==============================================================================

@pytest.mark.parametrize(
    "phrase",
    [
        "Now start the screen recording",
        "NOVA, close Sublime Text",
        "Browse the internet and search for most important books",
        "Please open YouTube for me",
        "shutdown nova",
        "what is the weather today",
        "can you list all files on desktop",
    ],
)
def test_quality_gate_accepts_natural_commands(phrase: str) -> None:
    """Test 4: Genuine intentional speech commands pass the quality gate."""
    gate = TranscriptQualityGate()

    speech_res = TranscriptionResult(
        text=phrase,
        confidence=0.92,
        no_speech_prob=0.02,
        avg_logprob=-0.25,
        compression_ratio=1.2,
        speech_duration=2.1,
    )

    eval_result = gate.evaluate(speech_res)
    assert eval_result.accepted
    assert eval_result.decision == QualityDecision.ACCEPTED
    assert eval_result.is_command_candidate
    assert eval_result.confidence >= 0.70


# ==============================================================================
# TEST 5: Flagging Uncertain Speech for Confirmation
# ==============================================================================

def test_quality_gate_flags_uncertain_speech() -> None:
    """Test 5: Speech with marginal acoustic confidence is flagged as UNCERTAIN."""
    gate = TranscriptQualityGate(min_confidence=0.65)

    uncertain_res = TranscriptionResult(
        text="shutdown",
        confidence=0.52,
        no_speech_prob=0.15,
        avg_logprob=-0.65,
        compression_ratio=1.0,
        speech_duration=0.9,
    )

    eval_result = gate.evaluate(uncertain_res)
    assert eval_result.accepted  # Allowed through turn pipeline
    assert eval_result.decision == QualityDecision.UNCERTAIN  # Flagged for confirmation on destructive actions


# ==============================================================================
# TEST 6: VoiceManager Pipeline Gate Integration
# ==============================================================================

def test_voice_manager_discards_noise_and_passes_speech() -> None:
    """Test 6: VoiceManager rejects noise before invoking turn callback."""
    vm = VoiceManager()

    dispatched_turns: list[str] = []

    def on_text(res: TranscriptionResult) -> None:
        dispatched_turns.append(res.text)

    vm.start_listening(on_text)

    # 1. Simulate finalized speech that is pure noise / cough (returns high no_speech_prob)
    class MockNoiseTranscriber:
        name = "mock_noise"
        def transcribe(self, audio, sample_rate=16000, language=None):
            return TranscriptionResult(
                text="bye thank you",
                confidence=0.1,
                no_speech_prob=0.9,
                avg_logprob=-1.5,
                compression_ratio=1.0,
                duration_seconds=0.1,
            )

    vm.transcriber._active_transcriber = MockNoiseTranscriber()
    vm._handle_finalized_speech(np.zeros(8000, dtype=np.float32))

    # Noise should NOT be dispatched to turn queue
    assert len(dispatched_turns) == 0

    # 2. Simulate finalized speech that is a genuine natural command
    class MockSpeechTranscriber:
        name = "mock_speech"
        def transcribe(self, audio, sample_rate=16000, language=None):
            return TranscriptionResult(
                text="Now start the screen recording",
                confidence=0.95,
                no_speech_prob=0.01,
                avg_logprob=-0.15,
                compression_ratio=1.1,
                duration_seconds=0.1,
            )

    vm.transcriber._active_transcriber = MockSpeechTranscriber()
    vm._handle_finalized_speech(np.ones(16000, dtype=np.float32) * 0.1)

    # Valid speech MUST be dispatched
    assert len(dispatched_turns) == 1
    assert dispatched_turns[0] == "Now start the screen recording"

    vm.shutdown()


# ==============================================================================
# TEST 7: Local Command Router Safety (No casual 'bye' instant shutdown)
# ==============================================================================

def test_command_router_safety_from_casual_bye() -> None:
    """Test 7: Casual 'bye' does not trigger immediate application shutdown."""
    router = VoiceCommandRouter()
    shutdown_called = {"called": False}

    router.register_handler("shutdown", lambda: shutdown_called.update({"called": True}))

    # Casual "bye" or "bye thank you" is not in local shutdown keywords
    assert not router.route("bye")
    assert not router.route("bye thank you")
    assert not shutdown_called["called"]

    # Explicit command still works
    assert router.route("shutdown")
    assert shutdown_called["called"]
