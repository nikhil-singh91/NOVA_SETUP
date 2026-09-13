# 23 — System-Wide Data Flow & Interaction Lifecycles

## Overview
This document traces complete, concrete end-to-end data flows across every major modality in NOVA.

---

## 🎙️ 1. Voice Interaction Turn Flow
```
[User Utterance (Speech)]
         │
         ▼
`MicrophoneManager` (16kHz Audio Stream via PyAudio)
         │
         ▼
`VoiceActivityDetector` (Silero VAD / Energy Segmentation)
         │
         ▼
`AudioEventDetector` (Detects acoustic events like coughs/laughs, strips markers)
         │
         ▼
`TranscriptionManager` (Faster-Whisper localized ASR -> Transcript & Candidates)
         │
         ▼
`TranscriptQualityGate` (Discards noise/hallucinations, passes clean text)
         │
         ▼
`NovaApplication._turn_queue` (Pushes `TurnRequest(source='voice', ...)`)
         │
         ▼
`NovaApplication._process_turn` (Pulls request)
         │
         ▼
`NaturalLanguageIntentEngine` (Classifies CanonicalIntent & extracts parameters)
         │
         ▼
[Capability Execution or AI Provider Generation]
         │
         ▼
`ResponseOrchestrator` (Formats dual output: clean spoken audio vs rich display)
         ├──> `SpeakerManager.speak()` -> Audio Output (Edge-TTS / SoundDevice)
         └──> `DashboardStatsManager.record_nova()` -> Terminal & UI WebSocket
```

---

## 💻 2. Visual Goal Execution Flow (NOVA Eyes + Computer Agent)
```
[Visual Goal: "Click the Submit button"]
         │
         ▼
`ComputerAgent.execute_visual_goal(goal_text)`
         │
         ▼
`NovaEyesManager.observe_now()`
  ├── Quartz Capture: `CGWindowListCreateImage` -> In-Memory `MemoryFrame`
  ├── Accessibility: `AccessibilityInspector` -> `AXUIElement` hierarchy
  └── Vision OCR: Apple Silicon `VNRecognizeTextRequest` -> Text Bounding Boxes
         │
         ▼
`EyesTargetResolver` (Maps target label to Retina (x, y) coordinates)
         │
         ▼
`EyesInteractionManager` (Injects hardware-level Quartz `CGEvent` mouse click)
         │
         ▼
`EyesStateVerifier` (Re-observes screen state to confirm visual outcome)
         │
         ▼
`VisualResult(success=True, verified=True)` -> Spoken response & activity feed
```

---

## 📋 3. Autonomous Multi-Step Task Flow
```
[Complex Goal: "Create my_app project folder and open Google Chrome"]
         │
         ▼
`TaskPlanner.plan_goal()` -> LLM Goal Decomposition
  ├── Step 1: `fs.create_folder(name="my_app")`
  └── Step 2: `app.launch(app_name="Google Chrome")`
         │
         ▼
`TaskExecutor.execute_plan()`
  ├── Step 1 Dispatch -> `CapabilityRegistry.get('fs.create_folder').handler()`
  │     ├── Folder created at `~/Desktop/my_app`
  │     └── Verifier confirms directory exists -> Step 1 `SUCCESS`
  ├── Step 2 Dispatch -> `CapabilityRegistry.get('app.launch').handler()`
  │     ├── Chrome process launched
  │     └── Process check confirms running -> Step 2 `SUCCESS`
  └── Final `TaskResult(status=SUCCESS, steps_completed=2)` -> Delivery to user
```
