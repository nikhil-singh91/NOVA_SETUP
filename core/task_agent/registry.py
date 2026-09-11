"""Capability registry mapping validated NOVA actions to structured execution handlers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from core.logger import get_logger
from core.task_agent.models import RiskLevel, TaskContext

logger = get_logger(__name__)


@dataclass
class CapabilityDefinition:
    """Specification and execution handler for a single verified NOVA capability."""

    name: str
    subsystem: str
    description: str
    risk_level: RiskLevel
    handler: Callable[[dict[str, Any], TaskContext], dict[str, Any]]
    verifier: Callable[[dict[str, Any], dict[str, Any], TaskContext], bool] | None = None
    requires_confirmation: bool = False


class CapabilityRegistry:
    """Central catalog of all verified operations NOVA can perform."""

    def __init__(self) -> None:
        self._capabilities: dict[str, CapabilityDefinition] = {}
        self._register_default_capabilities()

    def register(self, cap: CapabilityDefinition) -> None:
        """Register a new verified capability."""
        self._capabilities[cap.name] = cap
        logger.debug("Registered capability: %s (%s)", cap.name, cap.subsystem)

    def get(self, name: str) -> CapabilityDefinition | None:
        """Retrieve capability definition by name."""
        return self._capabilities.get(name)

    def has(self, name: str) -> bool:
        """Check if capability exists."""
        return name in self._capabilities

    def list_capabilities(self) -> list[CapabilityDefinition]:
        """Return all registered capabilities."""
        return list(self._capabilities.values())

    # =========================================================================
    # DEFAULT CAPABILITY REGISTRATIONS
    # =========================================================================

    def _register_default_capabilities(self) -> None:
        """Register core filesystem, browser, desktop, visual, and screen tools."""

        # 1. Filesystem: Create Folder
        def _exec_create_folder(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from desktop.files import FileSystemManager
            name = params.get("name", "New Folder")
            on_desktop = params.get("on_desktop", True)
            parent_path = params.get("parent_path")

            # Resolve parent_path from TaskContext if 'it' or variable or named folder
            parent_dir: Path | None = None
            if isinstance(parent_path, str):
                if parent_path.lower() in ("it", "last_folder") and ctx.last_created_folder:
                    parent_dir = ctx.last_created_folder
                    on_desktop = False
                elif parent_path.lower() == "desktop":
                    parent_dir = Path.home() / "Desktop"
                    on_desktop = True
                elif parent_path.lower() in ctx.created_folders:
                    parent_dir = ctx.created_folders[parent_path.lower()]
                    on_desktop = False
                elif parent_path in ctx.created_folders:
                    parent_dir = ctx.created_folders[parent_path]
                    on_desktop = False
                else:
                    parent_dir = Path(parent_path)
                    on_desktop = False

            success, p, msg = FileSystemManager.create_folder(
                folder_name=name,
                parent=parent_dir,
                on_desktop=on_desktop,
            )
            if success:
                ctx.register_folder(name, p)
                return {"success": True, "path": str(p), "message": msg}
            return {"success": False, "error": msg}

        def _verify_create_folder(params: dict[str, Any], result: dict[str, Any], ctx: TaskContext) -> bool:
            if not result.get("success") or not result.get("path"):
                return False
            return Path(result["path"]).is_dir()

        self.register(
            CapabilityDefinition(
                name="fs.create_folder",
                subsystem="filesystem",
                description="Create a directory on Desktop or inside a specified parent folder.",
                risk_level=RiskLevel.LOW,
                handler=_exec_create_folder,
                verifier=_verify_create_folder,
            )
        )

        # 2. Filesystem: Create File
        def _exec_create_file(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from desktop.files import FileSystemManager
            name = params.get("name", "file.txt")
            content = params.get("content", "")
            parent_path = params.get("parent_path")

            parent_dir: Path | None = None
            if isinstance(parent_path, str):
                if parent_path.lower() in ("it", "last_folder") and ctx.last_created_folder:
                    parent_dir = ctx.last_created_folder
                elif parent_path.lower() == "desktop":
                    parent_dir = Path.home() / "Desktop"
                elif parent_path.lower() in ctx.created_folders:
                    parent_dir = ctx.created_folders[parent_path.lower()]
                elif parent_path in ctx.created_folders:
                    parent_dir = ctx.created_folders[parent_path]
                else:
                    parent_dir = Path(parent_path)

            success, created_paths, msg = FileSystemManager.create_files(
                file_names=[name],
                parent=parent_dir,
                content_map={name: content},
            )
            if success and created_paths:
                p = created_paths[0]
                ctx.register_file(name, p)
                return {"success": True, "path": str(p), "message": msg}
            return {"success": False, "error": msg}

        def _verify_create_file(params: dict[str, Any], result: dict[str, Any], ctx: TaskContext) -> bool:
            if not result.get("success") or not result.get("path"):
                return False
            return Path(result["path"]).is_file()

        self.register(
            CapabilityDefinition(
                name="fs.create_file",
                subsystem="filesystem",
                description="Create a source code file or document at a designated path.",
                risk_level=RiskLevel.LOW,
                handler=_exec_create_file,
                verifier=_verify_create_file,
            )
        )

        # 2B. Filesystem: Open Folder in Finder
        def _exec_open_folder(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            import subprocess
            from desktop.files import FileSystemManager
            name = params.get("name")
            target_path = params.get("path")
            if target_path:
                p = Path(target_path)
            elif name and name in ctx.created_folders:
                p = ctx.created_folders[name]
            elif ctx.last_created_folder:
                p = ctx.last_created_folder
            else:
                matches = FileSystemManager.find_folders_by_name(name or "")
                p = matches[0] if matches else Path.home() / "Desktop"

            subprocess.run(["open", str(p)], check=False)
            return {"success": True, "path": str(p), "message": f"Opened {p.name} in Finder."}

        self.register(
            CapabilityDefinition(
                name="fs.open_folder",
                subsystem="filesystem",
                description="Open a directory in macOS Finder.",
                risk_level=RiskLevel.LOW,
                handler=_exec_open_folder,
            )
        )

        # 3. Filesystem: Move to Trash (Destructive)
        def _exec_safe_trash(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from desktop.files import FileSystemManager
            fs_mgr = FileSystemManager()
            target = params.get("target_path")
            if not target:
                return {"success": False, "error": "No target path specified for deletion."}
            p = Path(target)
            res = fs_mgr.safe_move_to_trash(p)
            return {"success": res.success, "path": str(p), "message": res.message}

        def _verify_safe_trash(params: dict[str, Any], result: dict[str, Any], ctx: TaskContext) -> bool:
            p_str = result.get("path")
            if not p_str:
                return False
            return not Path(p_str).exists()

        self.register(
            CapabilityDefinition(
                name="fs.safe_move_to_trash",
                subsystem="filesystem",
                description="Safely move a file or directory to macOS Trash.",
                risk_level=RiskLevel.HIGH,
                handler=_exec_safe_trash,
                verifier=_verify_safe_trash,
                requires_confirmation=True,
            )
        )

        # 4. Document Writing via AI
        def _exec_doc_write(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from desktop.editor import DocumentEditor
            editor = DocumentEditor()
            topic = params.get("topic", "General Document")
            app_name = params.get("app_name", "TextEdit")
            res = editor.write_and_open_document(topic=topic, app_name=app_name)
            if res.success:
                doc_p = res.data.get("file_path")
                if doc_p:
                    ctx.register_file(Path(doc_p).name, Path(doc_p))
                return {"success": True, "path": doc_p, "message": res.message}
            return {"success": False, "error": res.message}

        self.register(
            CapabilityDefinition(
                name="doc.write_and_open",
                subsystem="document_writing",
                description="Generate an AI document and open it in a text editor.",
                risk_level=RiskLevel.LOW,
                handler=_exec_doc_write,
            )
        )

        # 5. Application Launch
        def _exec_launch_app(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from desktop.apps import ApplicationManager
            app_mgr = ApplicationManager()
            name = params.get("app_name", "")
            res = app_mgr.launch_application(name)
            if res.success:
                ctx.opened_apps.append(name)
                return {"success": True, "app_name": name, "message": res.message}
            return {"success": False, "error": res.message}

        self.register(
            CapabilityDefinition(
                name="app.launch",
                subsystem="desktop_app",
                description="Launch a standard macOS application.",
                risk_level=RiskLevel.LOW,
                handler=_exec_launch_app,
            )
        )

        # 6. Browser: Open Website
        def _exec_open_site(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from browser.manager import BrowserManager
            bm = BrowserManager()
            url = params.get("target_url", "")
            res = bm.execute_command(f"open {url}")
            if res:
                ctx.active_urls.append(url)
                return {"success": res.success, "url": url, "message": res.spoken_response}
            return {"success": False, "error": "Browser command failed."}

        self.register(
            CapabilityDefinition(
                name="browser.open_site",
                subsystem="browser",
                description="Navigate to a website URL in the browser.",
                risk_level=RiskLevel.LOW,
                handler=_exec_open_site,
            )
        )

        # 7. Browser: Web Search
        def _exec_search_web(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from browser.manager import BrowserManager
            bm = BrowserManager()
            query = params.get("query", "")
            res = bm.execute_command(f"search Google for {query}")
            if res:
                return {"success": res.success, "query": query, "message": res.spoken_response}
            return {"success": False, "error": "Search command failed."}

        self.register(
            CapabilityDefinition(
                name="browser.search_web",
                subsystem="browser",
                description="Search Google for a topic or query.",
                risk_level=RiskLevel.LOW,
                handler=_exec_search_web,
            )
        )

        # 8. Browser: Site Search
        def _exec_search_site(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from browser.manager import BrowserManager
            bm = BrowserManager()
            site = params.get("site", "flipkart")
            query = params.get("query", "")
            res = bm.execute_command(f"In {site} search {query}")
            if res:
                return {"success": res.success, "site": site, "query": query, "message": res.spoken_response}
            return {"success": False, "error": "In-site search failed."}

        self.register(
            CapabilityDefinition(
                name="browser.search_site",
                subsystem="browser",
                description="Perform an in-site product or article search on a supported website.",
                risk_level=RiskLevel.LOW,
                handler=_exec_search_site,
            )
        )

        # 9. Visual Interaction: Click UI Element
        def _exec_visual_click(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from core.computer_agent import computer_agent
            label = params.get("target_label", "")
            res = computer_agent.execute_visual_goal(label)
            return {"success": res.success, "verified": res.verified, "message": res.spoken_response}

        self.register(
            CapabilityDefinition(
                name="visual.click_element",
                subsystem="visual",
                description="Visually locate and click a UI element on screen.",
                risk_level=RiskLevel.MEDIUM,
                handler=_exec_visual_click,
            )
        )

        # 10. Visual Interaction: Type Text
        def _exec_visual_type(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from core.computer_agent import computer_agent
            text = params.get("text", "")
            target_label = params.get("target_label")
            submit = params.get("submit", False)
            res = computer_agent.type_into_focused_or_target(text, target_label=target_label, submit=submit)
            return {"success": res.success, "message": res.spoken_response}

        self.register(
            CapabilityDefinition(
                name="visual.type_text",
                subsystem="visual",
                description="Type text into active focus or target UI field.",
                risk_level=RiskLevel.LOW,
                handler=_exec_visual_type,
            )
        )

        # 11. Visual Interaction: Close Popup
        def _exec_close_popup(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from core.computer_agent import computer_agent
            res = computer_agent.close_popup()
            return {"success": res.success, "verified": res.verified, "message": res.spoken_response}

        self.register(
            CapabilityDefinition(
                name="visual.close_popup",
                subsystem="visual",
                description="Find and close an active modal popup or dialog.",
                risk_level=RiskLevel.LOW,
                handler=_exec_close_popup,
            )
        )

        # 12. Camera: Open Camera Viewfinder
        def _exec_open_camera(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from desktop.camera import CameraManager
            res = CameraManager().open_camera()
            return {"success": res.success, "message": res.spoken_response}

        self.register(
            CapabilityDefinition(
                name="camera.open_camera",
                subsystem="camera",
                description="Open macOS Photo Booth or camera viewfinder.",
                risk_level=RiskLevel.LOW,
                handler=_exec_open_camera,
            )
        )

        # 13. Camera: Capture Snapshot Photo
        def _exec_take_photo(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from desktop.camera import CameraManager
            out_p = params.get("output_path")
            res = CameraManager().capture_photo(output_path=Path(out_p) if out_p else None)
            return {"success": res.success, "path": res.data.get("path") if res.data else None, "message": res.spoken_response}

        self.register(
            CapabilityDefinition(
                name="camera.take_photo",
                subsystem="camera",
                description="Capture a photo snapshot from the connected camera.",
                risk_level=RiskLevel.LOW,
                handler=_exec_take_photo,
                verifier=lambda p, r, ctx: bool(r.get("success") and r.get("path") and Path(r["path"]).is_file()),
            )
        )

        # 14. Clipboard: Read
        def _exec_get_clipboard(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from mac_control.actions.clipboard import get_clipboard
            text = get_clipboard()
            return {"success": True, "text": text}

        self.register(
            CapabilityDefinition(
                name="clipboard.get",
                subsystem="clipboard",
                description="Read current text content from the system clipboard.",
                risk_level=RiskLevel.LOW,
                handler=_exec_get_clipboard,
            )
        )

        # 15. Clipboard: Write
        def _exec_set_clipboard(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from mac_control.actions.clipboard import set_clipboard
            text = params.get("text", "")
            set_clipboard(text)
            return {"success": True, "message": "Copied text to clipboard."}

        self.register(
            CapabilityDefinition(
                name="clipboard.set",
                subsystem="clipboard",
                description="Write text string to the system clipboard.",
                risk_level=RiskLevel.LOW,
                handler=_exec_set_clipboard,
            )
        )

        # 16. Clipboard: Clear
        def _exec_clear_clipboard(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from mac_control.actions.clipboard import clear_clipboard
            clear_clipboard()
            return {"success": True, "message": "Cleared clipboard."}

        self.register(
            CapabilityDefinition(
                name="clipboard.clear",
                subsystem="clipboard",
                description="Clear system clipboard content.",
                risk_level=RiskLevel.LOW,
                handler=_exec_clear_clipboard,
            )
        )

        # 17. System: Wi-Fi Control
        def _exec_wifi(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from mac_control.actions.wifi import set_wifi_power, get_wifi_status
            action = params.get("action", "status")
            if action == "on":
                success = set_wifi_power(True)
                return {"success": success, "status": "on"}
            elif action == "off":
                success = set_wifi_power(False)
                return {"success": success, "status": "off"}
            else:
                st = get_wifi_status()
                return {"success": True, "status": "on" if st else "off"}

        self.register(
            CapabilityDefinition(
                name="system.wifi",
                subsystem="system",
                description="Control or query Wi-Fi power state.",
                risk_level=RiskLevel.MEDIUM,
                handler=_exec_wifi,
            )
        )

        # 18. System: Bluetooth Control
        def _exec_bluetooth(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from mac_control.actions.bluetooth import set_bluetooth_power, get_bluetooth_status
            action = params.get("action", "status")
            if action == "on":
                success = set_bluetooth_power(True)
                return {"success": success, "status": "on"}
            elif action == "off":
                success = set_bluetooth_power(False)
                return {"success": success, "status": "off"}
            else:
                st = get_bluetooth_status()
                return {"success": True, "status": "on" if st else "off"}

        self.register(
            CapabilityDefinition(
                name="system.bluetooth",
                subsystem="system",
                description="Control or query Bluetooth power state.",
                risk_level=RiskLevel.MEDIUM,
                handler=_exec_bluetooth,
            )
        )

        # 19. Screen Recording: Start
        def _exec_record_start(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from core.screen_recording import screen_recording_manager
            success, msg = screen_recording_manager.start_recording()
            return {"success": success, "message": msg}

        self.register(
            CapabilityDefinition(
                name="screen.record_start",
                subsystem="screen_recording",
                description="Start background screen recording.",
                risk_level=RiskLevel.LOW,
                handler=_exec_record_start,
            )
        )

        # 20. Screen Recording: Stop
        def _exec_record_stop(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from core.screen_recording import screen_recording_manager
            success, msg, file_p = screen_recording_manager.stop_recording()
            return {"success": success, "path": str(file_p) if file_p else None, "message": msg}

        self.register(
            CapabilityDefinition(
                name="screen.record_stop",
                subsystem="screen_recording",
                description="Stop background screen recording and save video.",
                risk_level=RiskLevel.LOW,
                handler=_exec_record_stop,
                verifier=lambda p, r, ctx: bool(r.get("success") and r.get("path") and Path(r["path"]).is_file()),
            )
        )

        # 21. Screen Capture: Full Screenshot
        def _exec_screenshot_capture(params: dict[str, Any], ctx: TaskContext) -> dict[str, Any]:
            from core.screenshot import screenshot_service
            res = screenshot_service.capture_full_screen()
            return {
                "success": res.success,
                "path": str(res.file_path) if res.file_path else None,
                "filename": res.filename,
                "error": res.error,
                "message": f"Screenshot saved to {res.filename}" if res.success else (res.error or "Failed to take screenshot"),
            }

        self.register(
            CapabilityDefinition(
                name="screen.capture",
                subsystem="screen_capture",
                description="Capture a full screenshot and save to NOVA Screenshots on Desktop.",
                risk_level=RiskLevel.LOW,
                handler=_exec_screenshot_capture,
                verifier=lambda p, r, ctx: bool(r.get("success") and r.get("path") and Path(r["path"]).is_file()),
            )
        )


# Global singleton CapabilityRegistry
capability_registry = CapabilityRegistry()
