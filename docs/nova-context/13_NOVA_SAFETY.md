# 13 — NOVA Safety Architecture & Operation Guards

## Overview
NOVA enforces multi-tier safety checks across all filesystem, desktop, browser, and hardware interactions to prevent unintended damage, data loss, or unsafe execution.

---

## 🛡️ Safety Mechanisms

### 1. Mandatory Confirmation Gates
- **Destructive File Deletion:** Any request to delete or trash a file/folder (`DELETE_ITEM`) sets `pending_confirmation = {"action": "DELETE_ITEM", "target_path": ...}` and asks the user: *"Do you want me to delete [filename]?"*
- **System Shutdown:** Any shutdown request (`SYSTEM_SHUTDOWN`) triggers a confirmation gate when voice confidence is uncertain or command is received.
- **Confirmation State Resolver:** When `pending_confirmation` is active, affirmative responses ("yes", "haan", "sure", "proceed", "do it") execute the action; negative responses ("no", "cancel", "abort") immediately cancel and clear the state.

### 2. Filesystem Sandboxing (`desktop.safety.DesktopSafetyPolicy`)
- **Approved Roots Only:** Restricts write and delete operations strictly to user-owned spaces:
  - `~/Desktop`
  - `~/Documents`
  - `~/Downloads`
  - `~/Projects`
  - `~/Desktop/NOVA_WORKSPACE`
- **System Protection:** Absolute denial for system directories (`/System`, `/usr`, `/Library`, `/bin`, `/sbin`, `/etc`).
- **No Hard Overwrites:** File creation automatically generates versioned names (e.g. `file_1.txt`) unless overwrite is explicitly requested.

### 3. Browser Action Safety (`browser.safety.BrowserSafetyPolicy`)
- **Schema Filtering:** Blocks execution of dangerous protocol handlers (`javascript:`, `data:`, `file:`).
- **Sensitive Operations:** Flags high-risk actions (e-commerce purchase confirmations, password submissions) as requiring user interaction.

### 4. Immediate Cancellation
- All active execution loops (Task Agent, Computer Agent, Browser Manager) respect cancellation flags triggered by saying *"stop"*, *"cancel"*, or pressing Cancel in the UI.
