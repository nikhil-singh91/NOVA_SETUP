# 09 — NOVA Computer Control & UI Interaction

## Overview
NOVA's computer control subsystem (`core.computer_agent.ComputerAgent` and `core.eyes`) gives NOVA the ability to perceive and manipulate any macOS application using hardware-level events and native accessibility APIs.

---

## 🖱️ Interaction Capabilities

### 1. Quartz CGEvent Hardware Simulation
- **Retina-Aware Coordinates:** Maps logical window coordinates to physical display pixels taking Retina scale factors (`DisplayMetrics`) into account.
- **Mouse Clicks:** Injects single click, double click, and right click via `CGEventCreateMouseEvent(None, kCGEventLeftMouseDown, (x, y), kCGMouseButtonLeft)`.
- **Keyboard Typing:** Injects keystrokes and modifier combinations (Command, Option, Shift, Control) via `CGEventCreateKeyboardEvent`.
- **Scrolling:** Smooth pixel and line scrolling using `CGEventCreateScrollWheelEvent2`.

### 2. High-Level Visual Goals
- **`click_element(label)`:** Searches current screen state via OCR and Accessibility tree, identifies target bounding box, and clicks center.
- **`type_into_focused_or_target(text, label)`:** Focuses targeted input field or types directly into active cursor focus.
- **`close_popup()`:** Detects dialog close buttons ("✕", "Close", "Dismiss", "Cancel", "Not now") and dismisses popups.
- **`scroll_until_visible(text)`:** Repeatedly scrolls active window until target text appears in OCR bounding boxes.

---

## 🔄 The Computer Agent Loop
```
1. OBSERVE   -> Capture in-memory Quartz frame (`MemoryFrame`) + AXUIElement tree
2. UNDERSTAND-> Apple Vision OCR extracts text boxes; Accessibility parses UI buttons
3. PLAN      -> Spatial & semantic resolver identifies exact target coordinates
4. ACT       -> Injects Quartz CGEvent mouse click or keystroke sequence
5. VERIFY    -> Re-observes screen state to confirm UI delta or dismiss confirmation
```
