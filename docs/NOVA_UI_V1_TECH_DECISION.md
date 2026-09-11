# NOVA UI V1 Technology Stack & Architectural Decision

---

## 1. Executive Decision Summary

- **Frontend Application**: **React 18 + TypeScript + Vite**
- **Desktop Shell**: **Electron (macOS Native Window)**
- **Styling & Aesthetics**: **Modern Glassmorphic Dark Design System (Vanilla CSS / Tailwind Tokens)**
- **Avatar Engine**: **Layered Vector SVG + CSS Keyframes + Canvas Micro-Dynamics**
- **Backend Communication**: **Local WebSocket & REST IPC (`127.0.0.1:8765`)**
- **Backend Integration**: **Dedicated `backend_ui` Adapter Layer (Zero modifications to core NOVA subsystems)**

---

## 2. Evaluation: Electron vs. Tauri

| Criterion | Electron | Tauri | Decision Winner |
| :--- | :--- | :--- | :--- |
| **Python Process Management** | Native Node.js `child_process` with robust lifecycle binding, IPC pipes, and graceful kill signal handling. | Requires Rust FFI bindings and custom sidecar configuration. | **Electron** |
| **macOS Native Permissions** | Direct access to macOS permissions (Microphone, Camera, Screen, Accessibility) via Chromium and Cocoa bridges. | Requires separate macOS permissions integration in Rust. | **Electron** |
| **Real-time WebSockets & Audio Streams** | Native high-throughput WebSocket & WebAudio API support with zero Rust overhead. | Supported, but requires IPC bridging across Rust boundary. | **Electron** |
| **Developer Ergonomics & Reliability** | Battle-tested for desktop companion apps (VS Code, Slack, Discord); instant startup with Vite HMR. | Highly efficient binary size, but heavier build complexity with Rust toolchains. | **Electron** |

**Conclusion**: **Electron + React + TypeScript** provides the most reliable, seamless integration with our Python backend on macOS without introducing fragile cross-language FFI layers.

---

## 3. Avatar Rendering Architecture: 2.5D Vector SVG + Micro-Animation Engine

To achieve high visual quality, buttery-smooth 60fps performance, and low CPU usage:
1. **Layered Vector Anatomy**:
   - Background Halo & Ambient Particle Glow
   - Base Face Silhouette & Skin Gradient
   - Dynamic Eyebrows (Rotation and vertical translation based on mood)
   - Intelligent Expressive Eyes (Saccadic micro-movement, pupil dilation, animated eyelids for blinking and squinting)
   - State-Morphing Mouth (Bezier curve mouth line for smile, talking phoneme approximations, thinking neutral)
   - Dynamic Hair Accents & Cybernetic Headband Accents
2. **Avatar State Mapping**:
   - `IDLE`: Gentle sinusoidal breathing, periodic natural blinking (every 3-5s).
   - `LISTENING`: Attentive wide eyes, subtle head tilt, glowing turquoise listening ring.
   - `THINKING`: Elevated eyebrows, upward eye gaze, violet pulse animation.
   - `PLANNING`: Focused expression, organized neon nodes aura.
   - `EXECUTING`: Confident smile, subtle active particle stream.
   - `VERIFYING`: Focused downward inspection gaze, radar scan ring.
   - `SPEAKING`: Expressive mouth animation synced with speech state, natural eyelid dynamics.
   - `SUCCESS`: Radiant warm smile, emerald green aura.
   - `CONFUSED`: Asymmetrical eyebrow elevation, slight head tilt.
   - `ERROR`: Calm concerned gaze, amber/crimson indicator.
   - `OFFLINE`: Low-opacity monochrome sleep state.

---

## 4. Privacy & Security Invariants

- **Localhost Bound**: The backend server binds strictly to `127.0.0.1:8765` with tokenized session handshake. It never opens public network listeners.
- **Data Sanitization**: The `EventBridge` automatically filters API keys, system tokens, raw passwords, and binary screen captures before broadcasting to the UI.
- **Explicit Privacy Badges**: Real-time status indicators in the UI header indicate when the microphone is listening, camera is active, or screen observation is occurring.
