# NOVA UI V1 Manual Testing Checklist

---

## 1. Test Verification Matrix

| Step | Action | Expected Result | Pass / Fail |
| :--- | :--- | :--- | :---: |
| **1. Desktop Window Launch** | Start backend (`python ui/backend/launcher.py`) and run `npm run dev` in `ui/desktop`. | Window opens with dark glassmorphic UI, sidebar navigation, and online status badge. | 🟢 PASS |
| **2. Avatar Animation Check** | Observe avatar in Home screen while idle. | Avatar breathes sinusoidally, blinks every 3-5 seconds, and displays cyan mood glow. | 🟢 PASS |
| **3. Chat Command Submission** | In Chat screen, type `"Open VS Code"` and hit Enter or click Run. | User message appears immediately; avatar transitions to `thinking` $\rightarrow$ `executing` $\rightarrow$ `success`; turn result card displays completion status. | 🟢 PASS |
| **4. Quick Capability Pills** | On Home screen, click `"Create DSA Folder"`. | Command runs on backend; activity timeline logs the event; folder is created on Desktop. | 🟢 PASS |
| **5. Voice Hub Interaction** | Navigate to Voice tab and click the **Push To Talk** button. | Audio visualizer waveform pulses; mic privacy badge lights up in top bar; live transcript displays speech. | 🟢 PASS |
| **6. Multi-Step Task Visualization** | Submit a multi-step prompt: `"Create a folder called DSA Project on Desktop with Arrays and Trees folders"`. | Tasks tab displays active goal card with planned steps, animated running step spinner, and progressive progress bar. | 🟢 PASS |
| **7. Instant Task Cancellation** | While a task is running, click the top **STOP TASK** button or Voice **Cancel Task** button. | Active steps halt immediately; UI shows `Cancelled` banner; avatar returns to idle. | 🟢 PASS |
| **8. Privacy Badges** | Trigger screen recording or visual observation. | Top bar illuminates `RECORDING` / `OBSERVING SCREEN` badge with amber/rose pulse. | 🟢 PASS |
| **9. Backend Disconnect Resilience** | Terminate backend gateway process while UI is open. | Sidebar status turns red (`OFFLINE`); avatar enters sleep state; UI attempts automatic reconnection every 2.5s. | 🟢 PASS |
| **10. Permissions Dashboard** | Navigate to Security / Permissions tab. | Displays live status for Accessibility, Microphone, Screen Recording, Camera, and Automation with explanation guides. | 🟢 PASS |
