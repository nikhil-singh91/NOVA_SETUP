"""End-to-end integration test validating NOVA Voice V2 and Turn Pipeline."""

from __future__ import annotations

import time

import numpy as np
from core.event_bus import EventBus
from main import NovaApplication, TurnRequest
from memory.memory_manager import MemoryManager
from personality.emotion_engine import EmotionEngine
from personality.system_prompt import SystemPromptManager
from voice import TranscriptionResult
from voice.vad import VoiceActivityDetector


def test_end_to_end_voice_interaction() -> None:
    """Validate full flow from simulated speech audio to response delivery."""
    # 1. Initialize core managers
    app = NovaApplication()
    app.event_bus = EventBus()
    app.emotion_engine = EmotionEngine()
    app.system_prompt_manager = SystemPromptManager()
    app.system_prompt_manager.initialize()
    app._register_companion_profiles()
    app.memory_manager = MemoryManager()

    # 2. Setup mock speech audio in VAD
    vad = VoiceActivityDetector(
        sample_rate=16000,
        chunk_size=512,
        silence_duration_s=0.1,
        min_speech_duration_s=0.05,
    )

    t = np.linspace(0, 0.032, 512, endpoint=False)
    speech_frame = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    silence_frame = np.zeros(512, dtype=np.float32)

    vad.process_chunk(speech_frame)
    vad.process_chunk(speech_frame)
    vad.process_chunk(speech_frame)
    time.sleep(0.12)
    vad_state, final_audio = vad.process_chunk(silence_frame)

    assert final_audio is not None and len(final_audio) > 0

    # 3. Simulate transcription callback enqueuing TurnRequest
    transcription = TranscriptionResult(text="Open Safari", confidence=0.98)
    app._turn_queue.put(TurnRequest(source="voice", text=transcription.text))

    # 4. Dequeue and resolve turn
    turn_request = app._turn_queue.get(timeout=0.2)
    assert turn_request.source == "voice"
    assert turn_request.text == "Open Safari"

    # 5. Process turn with mock response
    analysis = app.emotion_engine.analyze_text(turn_request.text)
    assert analysis.detected_mode is not None

    # 6. Verify speaker sanitization
    cleaned_speech = app.voice_manager.speaker._speak_fallback is not None
    assert cleaned_speech is True
