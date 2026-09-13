# 18 — NOVA Filesystem Operations & Document Architecture

## Overview
Filesystem operations in NOVA are governed by `desktop.files.FileSystemManager` and `desktop.safety.DesktopSafetyPolicy`, ensuring robust file discovery, overwrite prevention, and safe trash handling.

---

## 📂 Core Filesystem Operations

### 1. Multi-Root Search & Resolution
`FileSystemManager.find_files_by_name()` and `find_folders_by_name()` dynamically resolve queries across approved safe directories:
- `~/Desktop`
- `~/Documents`
- `~/Downloads`
- `~/Projects`
- `~/Desktop/NOVA_WORKSPACE`

### 2. File & Directory Creation
- **Directory Creation:** `FileSystemManager.create_folder(name, parent, on_desktop)`.
- **File Creation:** `FileSystemManager.create_files(file_names, parent, content_map)`.
- **Safe Overwrite Protection:** Checks for existing paths and appends incremental suffixes (`name_1.ext`) unless explicit replacement is confirmed.

### 3. Safe Deletion & Trash Integration
- **Trash Integration:** `FileSystemManager.safe_move_to_trash(target_path)` uses macOS AppleScript or `send2trash` to move files to the system Trash bin rather than permanently unlinking (`os.remove`), preserving user recoverability.

### 4. AI Document Generation (`DocumentEditor`)
- **`write_and_open_document(topic, destination, filename)`:** Generates comprehensive, high-quality notes or essays via AI and automatically saves and launches them in TextEdit or user text editor.
