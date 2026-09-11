# Running & Building NOVA UI V1

---

## 1. Prerequisites

- Python 3.12+ (in active `.venv`)
- Node.js v18+ and npm
- macOS 12+ (Monterey, Ventura, Sonoma, Sequoia)

---

## 2. Quick Launch: Desktop Application

To start both the Python backend UI gateway and the Electron Desktop Window:

### Terminal 1: Launch Backend Gateway
```bash
source .venv/bin/activate
PYTHONPATH=. python ui/backend/launcher.py
```

### Terminal 2: Launch Frontend / Electron Window
```bash
cd ui/desktop
npm run dev
```
Open a browser at `http://127.0.0.1:5173` or launch native Electron:
```bash
cd ui/desktop
npm run electron:start
```

---

## 3. Development Scripts

Inside `ui/desktop/`:
- `npm run dev`: Starts Vite hot-reloading dev server at `http://127.0.0.1:5173`.
- `npm run build`: Type-checks and builds production assets into `dist/`.
- `npm run electron:start`: Opens native macOS Electron application window.

---

## 4. Diagnostic & Permission Check

To verify all system permissions before running:
```bash
PYTHONPATH=. python main.py doctor
```
