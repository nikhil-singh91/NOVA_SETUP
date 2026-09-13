# 07 — NOVA Voice V2 Subsystem Architecture

## Overview
NOVA Voice V2 provides a voice-first interaction pipeline with continuous background listening, energy-adaptive VAD, local speech recognition, acoustic non-speech event detection, quality filtering, and speech synthesis.

---

## 🎙️ Audio Processing Pipeline
```
[Microphone (PyAudio)] -> 16kHz Mono Stream
         │
         ▼
[Silero VAD / Energy Detector (`VoiceActivityDetector`)]
  ├── Silence / Noise Calibration
  ├── Min Speech Threshold (0.35s)
  └── Finalized Speech Segment Buffer
         │
         ▼
[Acoustic Audio Event Detector (`AudioEventDetector`)]
  ├── Intercepts non-speech events (cough, laugh, sneeze, sigh)
  └── Strips acoustic markers from transcript
         │
         ▼
[Faster-Whisper Transcriber (`TranscriptionManager`)]
  ├── Localized inference (model: small.en / base)
  ├── Generates candidate hypotheses & confidence
  └── Normalizes ASR artifacts & numbers
         │
         ▼
[Transcript Quality Gate (`TranscriptQualityGate`)]
  ├── Discards phantom hallucinations (e.g. repeated "Thank you" in silence)
  └── Evaluates confidence score threshold (>0.45)
         │
         ▼
[Local Command Recognizer (`CommandRecognizer` / `VoiceCommandRouter`)]
  ├── Instant route for "shutdown", "stop", "cancel"
  └── Passes natural language commands to `NovaApplication._turn_queue`
         │
         ▼
[Speech Synthesizer (`SpeakerManager`)]
  ├── Microsoft Edge-TTS (`hi-IN-SwaraNeural` or customizable)
  ├── Pygame Audio Mixer / SoundDevice playback
  └── Interruption / barge-in support
```

---

## ⚡ Key Voice Invariants
1. **TTS Cleanliness:** TTS input is stripped of emojis, markdown bullets, URLs, and code blocks before speaking via `ResponseOrchestrator.clean_for_speech()`.
2. **Audio Event Empathy:** Acoustic non-speech cues (coughs, sneezes) produce instant empathetic responses ("Bless you! You okay?") without LLM latency.
3. **Graceful Degradation:** If audio hardware or PortAudio is unavailable, NOVA automatically continues in typed console / UI mode with `voice_available = False`.
