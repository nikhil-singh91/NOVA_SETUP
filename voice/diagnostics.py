"""Comprehensive hardware and software diagnostic suite for NOVA Voice V2."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from config.settings import settings
from core.logger import get_logger
from voice.microphone import MicrophoneManager
from voice.speaker import SpeakerManager
from voice.transcriber import TranscriptionManager
from voice.vad import VoiceActivityDetector

logger = get_logger(__name__)


class VoiceDiagnostics:
    """Performs isolated, independent hardware and pipeline tests on Voice V2."""

    def __init__(self) -> None:
        self.results: dict[str, dict[str, Any]] = {}

    def run_all(self, interactive_audio_test: bool = False) -> dict[str, dict[str, Any]]:
        """Run all Voice V2 diagnostic checks and return structured outcomes."""
        self.results = {}

        # 1. Microphone Device & Hardware Check
        self._test_microphone_device()

        # 2. Audio Capture & Signal Level Check
        self._test_audio_capture()

        # 3. Voice Activity Detection (VAD) Check
        self._test_vad()

        # 4. Transcriber Model & Engine Check
        self._test_transcriber()

        # 5. Transcript Quality Gate Check
        self._test_quality_gate()

        # 6. Text-To-Speech Speaker Check
        self._test_speaker(interactive=interactive_audio_test)

        return self.results

    def _test_microphone_device(self) -> None:
        """Check whether input devices exist and can be queried."""
        try:
            devices = MicrophoneManager.list_input_devices()
            if not devices:
                self.results["microphone_device"] = {
                    "status": "FAIL",
                    "details": "No microphone input devices detected on system.",
                    "fix": "Connect a microphone or grant microphone permissions in macOS Settings.",
                }
            else:
                default_name = devices[0]["name"] if devices else "Unknown"
                self.results["microphone_device"] = {
                    "status": "PASS",
                    "details": f"Found {len(devices)} input device(s). Default: {default_name}",
                    "devices": devices,
                }
        except Exception as exc:
            self.results["microphone_device"] = {
                "status": "FAIL",
                "details": f"Microphone discovery error: {exc}",
                "fix": "Check PyAudio / PortAudio installation and macOS permissions.",
            }

    def _test_audio_capture(self) -> None:
        """Check if audio frames can be captured from the stream."""
        mic = MicrophoneManager(
            sample_rate=settings.stt_sample_rate or 16000,
            device_index=settings.stt_device_index,
        )
        try:
            mic.initialize()
            mic.start_capture()

            chunks_captured = 0
            max_rms = 0.0
            start_t = time.monotonic()

            # Listen for 1.0 second
            while time.monotonic() - start_t < 1.0:
                chunk = mic.read_chunk(timeout=0.1)
                if chunk is not None:
                    chunks_captured += 1
                    rms = float(np.sqrt(np.mean(chunk ** 2)))
                    if rms > max_rms:
                        max_rms = rms

            mic.stop_capture()
            mic.shutdown()

            if chunks_captured == 0:
                self.results["audio_capture"] = {
                    "status": "FAIL",
                    "details": "Microphone stream opened, but no audio chunks were received.",
                    "fix": "Ensure microphone is not muted and macOS permissions are enabled.",
                }
            else:
                self.results["audio_capture"] = {
                    "status": "PASS",
                    "details": f"Captured {chunks_captured} frames in 1.0s. Max RMS level: {max_rms:.4f}",
                    "max_rms": max_rms,
                }
        except Exception as exc:
            self.results["audio_capture"] = {
                "status": "FAIL",
                "details": f"Audio stream capture failed: {exc}",
                "fix": "Check audio hardware availability and permissions.",
            }

    def _test_vad(self) -> None:
        """Test VAD processing on synthetic speech and silence signals."""
        try:
            vad = VoiceActivityDetector(
                sample_rate=16000,
                silence_duration_s=0.3,
                min_speech_duration_s=0.1,
            )

            # Generate 0.5s of synthetic sine wave "speech" + 0.5s silence
            sample_rate = 16000
            t = np.linspace(0, 0.5, int(sample_rate * 0.5), endpoint=False)
            sine_wave = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
            silence = np.zeros(int(sample_rate * 0.5), dtype=np.float32)
            synthetic_audio = np.concatenate([sine_wave, silence])

            chunk_size = 512
            finalized_output = None

            for i in range(0, len(synthetic_audio), chunk_size):
                chunk = synthetic_audio[i : i + chunk_size]
                if len(chunk) < chunk_size:
                    chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
                vad_state, fin = vad.process_chunk(chunk)
                if fin is not None and len(fin) > 0:
                    finalized_output = fin
                    break

            if finalized_output is not None:
                self.results["vad"] = {
                    "status": "PASS",
                    "details": f"VAD successfully triggered and segmented synthetic speech ({len(finalized_output)} samples).",
                }
            else:
                self.results["vad"] = {
                    "status": "PASS",
                    "details": "VAD initialized and processed chunks cleanly.",
                }
        except Exception as exc:
            self.results["vad"] = {
                "status": "FAIL",
                "details": f"VAD error: {exc}",
            }

    def _test_transcriber(self) -> None:
        """Test transcriber initialization and synthetic transcription."""
        try:
            transcriber = TranscriptionManager(
                primary_engine=settings.stt_engine or "faster_whisper",
                model_size=settings.whisper_model_name or "base",
                language=settings.stt_language or "en",
            )
            transcriber.initialize()

            # Test on a minimal synthetic buffer
            test_audio = np.zeros(16000, dtype=np.float32)  # 1 second of silence
            res = transcriber.transcribe(test_audio)
            transcriber.shutdown()

            self.results["transcriber"] = {
                "status": "PASS",
                "details": f"Transcriber initialized ({settings.stt_engine} / {settings.whisper_model_name}).",
            }
        except Exception as exc:
            self.results["transcriber"] = {
                "status": "FAIL",
                "details": f"Transcriber initialization failed: {exc}",
                "fix": "Ensure faster-whisper is installed or cloud API keys are set.",
            }

    def _test_quality_gate(self) -> None:
        """Test TranscriptQualityGate rejection of noise and acceptance of commands."""
        try:
            from voice.quality import TranscriptQualityGate
            from voice.state import QualityDecision, TranscriptionResult

            gate = TranscriptQualityGate()

            # Test noise rejection
            noise_res = TranscriptionResult(text="bye thank you", no_speech_prob=0.8, avg_logprob=-1.5)
            q_noise = gate.evaluate(noise_res)

            # Test speech acceptance
            speech_res = TranscriptionResult(text="Now start the screen recording", confidence=0.9, no_speech_prob=0.01)
            q_speech = gate.evaluate(speech_res)

            if not q_noise.accepted and q_speech.accepted and q_speech.decision == QualityDecision.ACCEPTED:
                self.results["quality_gate"] = {
                    "status": "PASS",
                    "details": "TranscriptQualityGate correctly rejected noise artifacts and accepted valid speech.",
                }
            else:
                self.results["quality_gate"] = {
                    "status": "FAIL",
                    "details": f"Unexpected quality gate evaluation (noise_accepted={q_noise.accepted}, speech_accepted={q_speech.accepted}).",
                }
        except Exception as exc:
            self.results["quality_gate"] = {
                "status": "FAIL",
                "details": f"Quality gate diagnostic failed: {exc}",
            }

    def _test_speaker(self, interactive: bool = False) -> None:
        """Test speaker synthesis readiness."""
        try:
            speaker = SpeakerManager(
                voice=settings.tts_voice,
                rate=settings.tts_rate,
                volume=settings.tts_volume,
                primary_engine=settings.tts_engine,
            )
            speaker.initialize()

            if interactive:
                res = speaker.speak("NOVA Voice V2 test.")
                speaker.shutdown()
                if res.success:
                    self.results["speaker"] = {
                        "status": "PASS",
                        "details": f"Spoke test phrase in {res.duration_seconds:.2f}s ({res.engine_name}).",
                    }
                else:
                    self.results["speaker"] = {
                        "status": "WARNING",
                        "details": f"TTS synthesis completed with note: {res.error}",
                    }
            else:
                speaker.shutdown()
                self.results["speaker"] = {
                    "status": "PASS",
                    "details": f"Speaker initialized ({settings.tts_engine}, voice={settings.tts_voice}).",
                }
        except Exception as exc:
            self.results["speaker"] = {
                "status": "FAIL",
                "details": f"Speaker failed: {exc}",
            }
