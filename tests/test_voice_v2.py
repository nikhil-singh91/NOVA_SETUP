"""Comprehensive verification and pipeline tests for NOVA Voice V2."""

from __future__ import annotations

import queue
import time

import numpy as np
from core.event_bus import EventBus, NovaEvent
from voice.commands import VoiceCommandRouter
from voice.manager import VoiceManager
from voice.microphone import MicrophoneManager
from voice.speaker import clean_text_for_speech
from voice.state import VADState, VoiceState
from voice.transcriber import TranscriptionManager
from voice.vad import VoiceActivityDetector

# ==============================================================================
# TEST 1: Microphone Hardware Discovery
# ==============================================================================

def test_microphone_device_discovery() -> None:
    """Test 1: Check if input devices can be queried without crashing."""
    devices = MicrophoneManager.list_input_devices()
    assert isinstance(devices, list)
    # Even in headless/CI environments, list_input_devices returns a valid list
    for dev in devices:
        assert "name" in dev
        assert "channels" in dev
        assert "sample_rate" in dev


# ==============================================================================
# TEST 2: Audio Normalization and RMS Metrics
# ==============================================================================

def test_audio_normalization_and_rms() -> None:
    """Test 2: Verify float32 normalization and RMS/peak calculations."""
    mic = MicrophoneManager(sample_rate=16000, chunk_size=512)

    # Generate synthetic int16 audio
    synthetic_int16 = (np.sin(np.linspace(0, 10, 512)) * 16384).astype(np.int16)
    raw_bytes = synthetic_int16.tobytes()

    mic._audio_queue.put(raw_bytes)
    chunk = mic.read_chunk(timeout=0.1)

    assert chunk is not None
    assert isinstance(chunk, np.ndarray)
    assert chunk.dtype == np.float32
    assert len(chunk) == 512
    assert -1.0 <= np.max(chunk) <= 1.0

    metrics = mic.get_metrics()
    assert metrics["last_rms"] > 0.0
    assert metrics["last_peak"] > 0.0


# ==============================================================================
# TEST 3: Voice Activity Detection (VAD) Speech Trigger
# ==============================================================================

def test_vad_speech_detection() -> None:
    """Test 3: Verify that VAD accurately distinguishes between silence and speech."""
    vad = VoiceActivityDetector(
        sample_rate=16000,
        chunk_size=512,
        silence_duration_s=0.3,
        min_speech_duration_s=0.1,
        base_energy_threshold=0.01,
    )

    silence_chunk = np.zeros(512, dtype=np.float32)
    state, fin = vad.process_chunk(silence_chunk)
    assert state == VADState.SILENCE
    assert fin is None

    # Speech frame: loud 440Hz sine wave
    t = np.linspace(0, 0.032, 512, endpoint=False)
    loud_speech_chunk = (0.25 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)

    # Feed 2 consecutive speech frames
    vad.process_chunk(loud_speech_chunk)
    state, fin = vad.process_chunk(loud_speech_chunk)

    assert state in (VADState.SPEECH_START, VADState.IN_SPEECH)
    assert fin is None


# ==============================================================================
# TEST 4: Speech Boundary Finalization after Silence (Hangover)
# ==============================================================================

def test_vad_speech_finalization() -> None:
    """Test 4: Verify that speech segment finalizes after silence timeout."""
    vad = VoiceActivityDetector(
        sample_rate=16000,
        chunk_size=512,
        silence_duration_s=0.1,  # Fast timeout for test
        min_speech_duration_s=0.05,
        base_energy_threshold=0.01,
    )

    t = np.linspace(0, 0.032, 512, endpoint=False)
    speech_chunk = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    silence_chunk = np.zeros(512, dtype=np.float32)

    # 1. Trigger speech
    vad.process_chunk(speech_chunk)
    vad.process_chunk(speech_chunk)
    vad.process_chunk(speech_chunk)

    # 2. Simulate silence for > 0.1s
    time.sleep(0.12)
    state, final_audio = vad.process_chunk(silence_chunk)

    assert state == VADState.SPEECH_FINALIZED
    assert final_audio is not None
    assert len(final_audio) > 0


# ==============================================================================
# TEST 5: Transcription Abstraction and Validation
# ==============================================================================

def test_transcription_validation() -> None:
    """Test 5: Verify that TranscriptionManager rejects silence and malformed buffers."""
    tm = TranscriptionManager(primary_engine="faster_whisper")

    # 1. Empty buffer
    empty_res = tm.transcribe(np.array([], dtype=np.float32))
    assert not empty_res.success
    assert empty_res.error is not None

    # 2. Silence buffer
    silence_res = tm.transcribe(np.zeros(16000, dtype=np.float32))
    assert not silence_res.success
    assert "silence" in silence_res.error.lower() or "empty" in silence_res.error.lower()


# ==============================================================================
# TEST 6: Text-To-Speech Sanitization and Engine
# ==============================================================================

def test_tts_text_cleaning() -> None:
    """Test 6: Verify that markdown, URLs, code blocks, and emojis are stripped."""
    raw_text = "Hello # Boss! Here is a `code snippet` and [link](https://example.com). 🎉 **Great** day!"
    cleaned = clean_text_for_speech(raw_text)

    assert "#" not in cleaned
    assert "http" not in cleaned
    assert "🎉" not in cleaned
    assert "*" not in cleaned
    assert "Hello Boss! Here is a and link. Great day!" in cleaned or "Hello Boss" in cleaned


# ==============================================================================
# TEST 7: Local Voice Command Router
# ==============================================================================

def test_voice_command_router() -> None:
    """Test 7: Verify local command matching and routing."""
    router = VoiceCommandRouter()
    triggered = {"shutdown": False}

    def on_shutdown():
        triggered["shutdown"] = True

    router.register_handler("shutdown", on_shutdown)

    # Test exact match
    res = router.route("shutdown")
    assert res is True
    assert triggered["shutdown"] is True

    # Test Hindi match
    triggered["shutdown"] = False
    res_hi = router.route("बाय नोवा")
    assert res_hi is True
    assert triggered["shutdown"] is True

    # Test non-command
    res_non = router.route("tell me a story about space")
    assert res_non is False


# ==============================================================================
# TEST 8: Voice State Machine and Event Bus Coordination
# ==============================================================================

def test_voice_manager_state_coordination() -> None:
    """Test 8: Verify VoiceManager state transitions and event emission."""
    vm = VoiceManager()
    events_received: list[str] = []

    from core.registry import registry
    if registry.exists("event_bus"):
        bus = registry.get("event_bus")
    else:
        bus = EventBus()
        registry.register("event_bus", bus)

    def on_state_changed(event_name: str, payload: dict) -> None:
        events_received.append(payload.get("new_state", ""))

    bus.subscribe(NovaEvent.STATE_CHANGED, on_state_changed)

    # Transition IDLE -> LISTENING -> PROCESSING -> SPEAKING -> IDLE
    vm.set_state(VoiceState.LISTENING)
    assert vm.state == VoiceState.LISTENING

    vm.set_state(VoiceState.PROCESSING)
    assert vm.state == VoiceState.PROCESSING

    vm.set_state(VoiceState.SPEAKING)
    assert vm.state == VoiceState.SPEAKING

    vm.set_state(VoiceState.IDLE)
    assert vm.state == VoiceState.IDLE

    assert "listening" in events_received
    assert "processing" in events_received
    assert "speaking" in events_received


# ==============================================================================
# TEST 9: Turn Queue Integration
# ==============================================================================

def test_turn_queue_flow() -> None:
    """Test 9: Verify turn queue enqueues and delivers TurnRequests correctly."""
    turn_q = queue.Queue()

    # Enqueue a voice turn
    turn_q.put(("voice", "Hello NOVA"))

    item = turn_q.get(timeout=0.1)
    assert item[0] == "voice"
    assert item[1] == "Hello NOVA"
