# NOVA Female AI Avatar & Expression State Engine

---

## 1. Persona & Visual Philosophy

NOVA's avatar is an **original, fictional female AI entity** designed with a holographic, futuristic aesthetic. She is the visual embodiment of NOVA—intelligent, calm, elegant, and responsive.

---

## 2. Core Visual States & Expressions

| Avatar State | Facial Expression Dynamics | Mood Glow & Ambient Halo | Behavioral Trigger |
| :--- | :--- | :--- | :--- |
| **`IDLE`** | Neutral friendly smile, gentle sinusoidal breathing (3.5s), periodic blinking (every ~4s). | Cyber Cyan (`#00f0ff`) | Standby / listening for wake word |
| **`LISTENING`** | Alert eyes, focused gaze, expanded outer dashed ring. | Electric Turquoise (`#06b6d4`) | Audio VAD active / Speech incoming |
| **`THINKING`** | Elevated left eyebrow, slightly upward eye gaze, subtle processing pulse. | Electric Violet (`#a855f7`) | Intent parsing & AI generation |
| **`PLANNING`** | Focused expression, structured energy nodes aura. | Deep Indigo (`#6366f1`) | Autonomous Task Agent planning steps |
| **`EXECUTING`** | Confident gaze, active particle stream. | Azure Blue (`#3b82f6`) | Performing browser/desktop/file actions |
| **`VERIFYING`** | Downward inspection gaze, checking visual state. | Mint Teal (`#14b8a6`) | VisualVerifier / ComputerAgent checking screen |
| **`SPEAKING`** | Dynamic mouth phoneme animation synced to TTS audio frames. | Brilliant Cyan (`#00f0ff`) | Kokoro / Piper speech synthesis playing |
| **`SUCCESS`** | Warm, radiant smile, relaxed eyelids. | Emerald Green (`#10b981`) | Command or task completed successfully |
| **`CONFUSED`** | Asymmetrical eyebrow tilt, slight questioning mouth angle. | Warm Amber (`#f59e0b`) | Ambiguous intent / asking for clarification |
| **`ERROR`** | Calm concerned expression, downward eyebrow angle. | Crimson Red (`#ef4444`) | Tool failure / missing permission |
| **`OFFLINE`** | Sleep state, closed eyelids, dim monochrome halo. | Slate Gray (`#64748b`) | Backend disconnected / standby |

---

## 3. High-Performance Vector Rendering

1. **Lightweight Vector SVG**: Zero heavy 3D rendering engines or heavy WebGL textures required; runs at 60fps with under 1% CPU utilization on macOS.
2. **Layered Anatomy**:
   - Background Halo & Particle Field
   - Hair Back Silhouette with gradient fill
   - Face Base with soft holographic lighting
   - Cybernetic Headband Accents
   - Dynamic Eyebrow paths
   - Multi-layer Eyes with pupils, reflection highlights, and animated eyelids
   - State-morphing Bezier Mouth
   - Front Hair Strands & Bangs
