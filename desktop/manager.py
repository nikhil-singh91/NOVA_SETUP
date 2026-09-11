"""Central coordinator for desktop operations, application launching, safe files, and interactive confirmations."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from core.event_bus import NovaEvent
from core.logger import get_logger
from core.registry import registry
from desktop.apps import AppLauncher
from desktop.camera import CameraManager
from desktop.code import CodeProjectManager
from desktop.context import DesktopContextManager
from desktop.editor import DocumentEditor
from desktop.files import FileSystemManager
from desktop.models import (
    DesktopActionPlan,
    DesktopActionType,
    DesktopResult,
    DesktopTaskPlan,
)
from desktop.parser import DesktopIntentParser
from desktop.planner import DesktopTaskPlanner
from desktop.safety import DesktopSafetyPolicy

logger = get_logger(__name__)


def log_desktop_diagnostics(action_name: str, status: str, **kwargs: Any) -> None:
    """Formatted trace logger for desktop execution operations."""
    details = " | ".join(f"{k}={v}" for k, v in kwargs.items())
    logger.info("🖥️ [DESKTOP EXECUTION] %s -> %s %s", action_name, status, f"({details})" if details else "")


class DesktopActionManager:
    """Thread-safe facade coordinating application management, filesystem operations, and bounded workflows."""

    def __init__(self) -> None:
        self.context_mgr = DesktopContextManager()
        self.planner = DesktopTaskPlanner()
        self.camera_mgr = CameraManager()
        self._lock = threading.RLock()
        self._stop_requested = threading.Event()
        self._is_initialized = True

    def initialize(self) -> None:
        """Initialize desktop manager resources."""
        with self._lock:
            self._is_initialized = True
            logger.info("DesktopActionManager initialized.")

    def _publish_event(self, event: NovaEvent, **payload: Any) -> None:
        try:
            if registry.exists("event_bus"):
                bus = registry.get("event_bus")
                bus.publish(event, **payload)
        except Exception as exc:
            logger.debug("Failed to publish event %s: %s", event.value, exc)

    def process_input(self, user_text: str) -> DesktopResult | None:
        """Parse natural language command, evaluate safety, and execute with structured diagnostics."""
        with self._lock:
            self._stop_requested.clear()
            plan_or_task = DesktopIntentParser.parse(user_text)
            if not plan_or_task:
                return None

            if isinstance(plan_or_task, DesktopTaskPlan):
                return self.planner.execute_plan(plan_or_task, stop_event=self._stop_requested)

            safe_plan = DesktopSafetyPolicy.evaluate(plan_or_task)
            return self._execute_single_action(safe_plan)

    def _execute_single_action(self, safe_plan: DesktopActionPlan) -> DesktopResult:
        """Execute a single DesktopActionPlan with boundary checks and confirmation awareness."""
        from core.environment import environment_observer, ContextResolver
        from ui.health_checker import DashboardStatsManager

        # 1. OPEN APPLICATION
        if safe_plan.action_type == DesktopActionType.OPEN_APP:
            DashboardStatsManager.record_understood("Open Application", details={"Target": safe_plan.app_name})
            DashboardStatsManager.record_action(f"Opening {safe_plan.app_name}")
            start_t = time.monotonic()
            success, msg, spoken = AppLauncher.launch(safe_plan.app_name)
            lat_ms = (time.monotonic() - start_t) * 1000
            log_desktop_diagnostics("OPEN_APP", "SUCCESS" if success else "FAILED", app=safe_plan.app_name, message=msg)
            if success:
                self.context_mgr.register_opened_app(safe_plan.app_name)
                DashboardStatsManager.record_result(f"✓ {safe_plan.app_name} opened successfully", success=True)
            else:
                DashboardStatsManager.record_result(f"✗ Could not open {safe_plan.app_name}: {msg}", success=False)
            DashboardStatsManager.record_mac_action(
                command_text=f"Open {safe_plan.app_name}",
                intent="application.open",
                target=safe_plan.app_name,
                status="SUCCESS" if success else "FAILED",
                latency_ms=lat_ms,
                result_message=msg or spoken,
            )
            return DesktopResult(success=success, action_type=safe_plan.action_type, message=msg, spoken_response=spoken)

        # 2. CLOSE APPLICATION
        if safe_plan.action_type == DesktopActionType.CLOSE_APP:
            DashboardStatsManager.record_understood("Close Application", details={"Target": safe_plan.app_name})
            DashboardStatsManager.record_action(f"Closing {safe_plan.app_name}")
            start_t = time.monotonic()
            success, msg, spoken = AppLauncher.close(safe_plan.app_name)
            lat_ms = (time.monotonic() - start_t) * 1000
            log_desktop_diagnostics("CLOSE_APP", "SUCCESS" if success else "FAILED", app=safe_plan.app_name, message=msg)
            if success:
                DashboardStatsManager.record_result(f"✓ {safe_plan.app_name} closed", success=True)
            else:
                DashboardStatsManager.record_result(f"✗ Could not close {safe_plan.app_name}: {msg}", success=False)
            DashboardStatsManager.record_mac_action(
                command_text=f"Close {safe_plan.app_name}",
                intent="application.close",
                target=safe_plan.app_name,
                status="SUCCESS" if success else "FAILED",
                latency_ms=lat_ms,
                result_message=msg or spoken,
            )
            return DesktopResult(success=success, action_type=safe_plan.action_type, message=msg, spoken_response=spoken)

        # 3. CREATE FOLDER
        if safe_plan.action_type == DesktopActionType.CREATE_FOLDER:
            location = safe_plan.metadata.get("location")
            on_desktop = bool(
                safe_plan.metadata.get("on_desktop")
                or "on desktop" in safe_plan.raw_prompt.lower()
                or "on my desktop" in safe_plan.raw_prompt.lower()
            )
            loc_desc = "Desktop" if (on_desktop or location == "desktop") else "filesystem"
            DashboardStatsManager.record_understood("Create Folder", details={"Target": safe_plan.target_name, "Location": loc_desc})
            DashboardStatsManager.record_action(f"Creating folder {safe_plan.target_name} on {loc_desc}")
            start_t = time.monotonic()
            success, path, msg = FileSystemManager.create_folder(
                safe_plan.target_name,
                location=location,
                on_desktop=on_desktop,
            )
            lat_ms = (time.monotonic() - start_t) * 1000
            log_desktop_diagnostics("CREATE_FOLDER", "SUCCESS" if success else "FAILED", folder=safe_plan.target_name, path=path)
            if success:
                self.context_mgr.set_active_project(path)
                DashboardStatsManager.record_result(f"✓ Folder created: {path}", success=True)
            else:
                DashboardStatsManager.record_result(f"✗ Could not create folder: {msg}", success=False)
            spoken = f"Created folder {safe_plan.target_name} {loc_desc}." if success else f"Could not create folder: {msg}"
            DashboardStatsManager.record_mac_action(
                command_text=f"Create folder {safe_plan.target_name}",
                intent="filesystem.folder.create",
                target=safe_plan.target_name,
                status="SUCCESS" if success else "FAILED",
                latency_ms=lat_ms,
                result_message=str(path) if success else msg,
            )
            return DesktopResult(success=success, action_type=safe_plan.action_type, message=msg, spoken_response=spoken, target_path=str(path))

        # 4. OPEN FOLDER
        if safe_plan.action_type == DesktopActionType.OPEN_FOLDER:
            DashboardStatsManager.record_understood("Open Folder", details={"Target": safe_plan.target_name or "Folder", "Location": "Desktop"})
            DashboardStatsManager.record_action(f"Searching Desktop for {safe_plan.target_name}")
            start_t = time.monotonic()
            target_folder_path: Path | None = None
            if safe_plan.target_path and Path(safe_plan.target_path).exists():
                target_folder_path = Path(safe_plan.target_path)
            elif safe_plan.metadata.get("use_context"):
                ctx = environment_observer.get_context()
                res = ContextResolver.resolve_target("it", ctx, target_type="folder")
                if res["resolved"] and isinstance(res["target"], Path):
                    target_folder_path = res["target"]
            elif safe_plan.target_name:
                matches = FileSystemManager.find_folders_by_name(safe_plan.target_name)
                if len(matches) == 1:
                    target_folder_path = matches[0]
                elif len(matches) > 1:
                    match_str = ", ".join(f"'{m.parent.name}/{m.name}'" for m in matches[:3])
                    spoken = f"I found multiple folders named {safe_plan.target_name}: {match_str}. Which one would you like to open?"
                    DashboardStatsManager.record_result(f"Found multiple matching folders: {match_str}", success=True)
                    DashboardStatsManager.record_mac_action(
                        command_text=f"Open folder {safe_plan.target_name}",
                        intent="filesystem.folder.open",
                        target=safe_plan.target_name,
                        status="SUCCESS",
                        latency_ms=(time.monotonic() - start_t) * 1000,
                        result_message=spoken,
                    )
                    return DesktopResult(
                        success=True,
                        action_type=safe_plan.action_type,
                        message=spoken,
                        spoken_response=spoken,
                        metadata={"multiple_matches": [str(m) for m in matches]},
                    )
                else:
                    DashboardStatsManager.record_result(f"✗ Folder not found: {safe_plan.target_name}", success=False)
                    spoken = f"I couldn't find a folder named '{safe_plan.target_name}' in your Desktop, Documents, or Downloads."
                    DashboardStatsManager.record_mac_action(
                        command_text=f"Open folder {safe_plan.target_name}",
                        intent="filesystem.folder.open",
                        target=safe_plan.target_name,
                        status="FAILED",
                        latency_ms=(time.monotonic() - start_t) * 1000,
                        result_message=spoken,
                    )
                    return DesktopResult(
                        success=False,
                        action_type=safe_plan.action_type,
                        error=spoken,
                        spoken_response=spoken,
                    )

            if target_folder_path and target_folder_path.exists():
                subprocess.run(["open", str(target_folder_path)], check=False)
                spoken = f"Opened {target_folder_path.name} folder in Finder."
                environment_observer.update_action_context(
                    action="OPEN_FOLDER",
                    opened_target=str(target_folder_path),
                )
                return DesktopResult(
                    success=True,
                    action_type=safe_plan.action_type,
                    message=spoken,
                    spoken_response=spoken,
                    target_path=str(target_folder_path),
                )
            else:
                spoken = f"Could not find the requested folder to open."
                return DesktopResult(
                    success=False,
                    action_type=safe_plan.action_type,
                    error=spoken,
                    spoken_response=spoken,
                )

        # 5. FIND ITEM (Files and Folders)
        if safe_plan.action_type == DesktopActionType.FIND_ITEM:
            query = safe_plan.target_name or safe_plan.metadata.get("query", "")
            matches = FileSystemManager.find_items(query)
            if len(matches) == 1:
                item = matches[0]
                spoken = f"I found '{item.name}' on your {item.parent.name} at {item}."
                return DesktopResult(
                    success=True,
                    action_type=safe_plan.action_type,
                    message=spoken,
                    spoken_response=spoken,
                    target_path=str(item),
                )
            elif len(matches) > 1:
                match_str = ", ".join(f"'{m.parent.name}/{m.name}'" for m in matches[:3])
                spoken = f"I found {len(matches)} items matching '{query}': {match_str}."
                return DesktopResult(
                    success=True,
                    action_type=safe_plan.action_type,
                    message=spoken,
                    spoken_response=spoken,
                    metadata={"multiple_matches": [str(m) for m in matches]},
                )
            else:
                spoken = f"I couldn't find any file or folder matching '{query}'."
                return DesktopResult(
                    success=False,
                    action_type=safe_plan.action_type,
                    error=spoken,
                    spoken_response=spoken,
                )

        # 6. OPEN FILE (with optional application)
        if safe_plan.action_type == DesktopActionType.OPEN_FILE:
            target_file_path: Path | None = None
            if safe_plan.target_path and Path(safe_plan.target_path).exists():
                target_file_path = Path(safe_plan.target_path)
            elif safe_plan.target_name:
                matches = FileSystemManager.find_files_by_name(safe_plan.target_name)
                if len(matches) == 1:
                    target_file_path = matches[0]
                elif len(matches) > 1:
                    match_str = ", ".join(f"'{m.parent.name}/{m.name}'" for m in matches[:3])
                    spoken = f"I found multiple files named {safe_plan.target_name}: {match_str}. Which one would you like to open?"
                    return DesktopResult(
                        success=True,
                        action_type=safe_plan.action_type,
                        message=spoken,
                        spoken_response=spoken,
                        metadata={"multiple_matches": [str(m) for m in matches]},
                    )
                else:
                    spoken = f"I couldn't find a file named '{safe_plan.target_name}' in your Desktop, Documents, or Downloads."
                    return DesktopResult(
                        success=False,
                        action_type=safe_plan.action_type,
                        error=spoken,
                        spoken_response=spoken,
                    )

            if target_file_path and target_file_path.exists():
                app_to_open = safe_plan.app_name or safe_plan.metadata.get("app_name")
                success, spoken = FileSystemManager.open_item(target_file_path, app_name=app_to_open)
                if success:
                    environment_observer.update_action_context(action="OPEN_FILE", opened_target=str(target_file_path))
                return DesktopResult(
                    success=success,
                    action_type=safe_plan.action_type,
                    message=spoken,
                    spoken_response=spoken,
                    target_path=str(target_file_path),
                )
            else:
                spoken = f"Could not find the requested file to open."
                return DesktopResult(success=False, action_type=safe_plan.action_type, error=spoken, spoken_response=spoken)

        # 7. RENAME ITEM
        if safe_plan.action_type == DesktopActionType.RENAME_ITEM:
            old_name = safe_plan.target_name
            new_name = safe_plan.metadata.get("new_name", "")
            success, new_p, msg = FileSystemManager.rename_item(old_name, new_name)
            log_desktop_diagnostics("RENAME_ITEM", "SUCCESS" if success else "FAILED", old=old_name, new=new_name)
            return DesktopResult(
                success=success,
                action_type=safe_plan.action_type,
                message=msg,
                spoken_response=msg,
                target_path=str(new_p) if new_p else "",
            )

        # 8. DELETE ITEM (Safe Move to Trash with Confirmation)
        if safe_plan.action_type == DesktopActionType.DELETE_ITEM:
            target_path_to_delete: Path | None = None
            if safe_plan.target_path and Path(safe_plan.target_path).exists():
                target_path_to_delete = Path(safe_plan.target_path)
            elif safe_plan.target_name:
                matches = FileSystemManager.find_items(safe_plan.target_name)
                if len(matches) == 1:
                    target_path_to_delete = matches[0]
                elif len(matches) > 1:
                    match_str = ", ".join(f"'{m.parent.name}/{m.name}'" for m in matches[:3])
                    spoken = f"I found multiple items named {safe_plan.target_name}: {match_str}. Which one would you like to delete?"
                    return DesktopResult(success=False, action_type=safe_plan.action_type, error=spoken, spoken_response=spoken)
            else:
                ctx = environment_observer.get_context()
                res = ContextResolver.resolve_target("this", ctx, target_type="any")
                if res["resolved"] and isinstance(res["target"], Path):
                    target_path_to_delete = res["target"]

            if not target_path_to_delete or not target_path_to_delete.exists():
                spoken = "What would you like me to delete? Please specify a file or folder."
                return DesktopResult(success=False, action_type=safe_plan.action_type, error=spoken, spoken_response=spoken)

            # Interactive Confirmation Gate
            item_type = "folder" if target_path_to_delete.is_dir() else "file"
            spoken = f"I found the {item_type} {target_path_to_delete.name} on your {target_path_to_delete.parent.name}. Do you want me to move it to Trash?"
            
            # Register pending confirmation state
            ctx = environment_observer.get_context()
            ctx.pending_confirmation = {
                "action": "DELETE_ITEM",
                "target_path": str(target_path_to_delete),
                "original_request": safe_plan.raw_prompt,
            }

            return DesktopResult(
                success=True,
                action_type=safe_plan.action_type,
                message=spoken,
                spoken_response=spoken,
                target_path=str(target_path_to_delete),
                requires_confirmation=True,
                confirmation_prompt=spoken,
            )

        # 9. CREATE FILES
        if safe_plan.action_type == DesktopActionType.CREATE_FILES:
            location = safe_plan.metadata.get("location")
            parent_target = safe_plan.metadata.get("parent_target", "").strip()

            parent_dir: Path | None = None
            if parent_target in ("it", "the folder i just created", "created folder", "this folder", "current folder"):
                ctx = environment_observer.get_context()
                res = ContextResolver.resolve_target("it", ctx, target_type="folder")
                if res["resolved"] and isinstance(res["target"], Path):
                    parent_dir = res["target"]
            elif parent_target and parent_target.lower() not in ("desktop", "the desktop", "my desktop", "documents", "my documents", "downloads", "my downloads"):
                matches = FileSystemManager.find_folders_by_name(parent_target)
                if matches:
                    parent_dir = matches[0]

            files_to_create = safe_plan.file_names if safe_plan.file_names else ([safe_plan.target_name] if safe_plan.target_name else [])
            content_map = safe_plan.metadata.get("content_map", {})
            success, paths, msg = FileSystemManager.create_files(
                files_to_create,
                parent=parent_dir,
                location=location,
                content_map=content_map,
            )
            log_desktop_diagnostics("CREATE_FILES", "SUCCESS" if success else "FAILED", files=files_to_create, count=len(paths))
            if success:
                self.context_mgr.register_created_files(paths)
            spoken = msg
            return DesktopResult(
                success=success,
                action_type=safe_plan.action_type,
                message=msg,
                spoken_response=spoken,
                target_path=str(paths[0]) if paths else "",
            )

        # 10. WRITE CODE FILE
        if safe_plan.action_type == DesktopActionType.WRITE_CODE_FILE:
            active_dir = self.context_mgr.get_active_directory()
            fname = safe_plan.file_names[0] if safe_plan.file_names else "main.py"
            code_body = CodeProjectManager.generate_code_content(safe_plan.content_topic, language=safe_plan.code_language or "python")
            success, paths, msg = FileSystemManager.create_files([fname], parent=active_dir, content_map={fname: code_body}, overwrite=True)
            log_desktop_diagnostics("WRITE_CODE_FILE", "SUCCESS" if success else "FAILED", file=fname, topic=safe_plan.content_topic)
            spoken = f"Created {fname} with {safe_plan.content_topic} program."
            return DesktopResult(success=success, action_type=safe_plan.action_type, message=msg, spoken_response=spoken, target_path=str(paths[0]) if paths else "")

        # 11. CREATE CODE PROJECT
        if safe_plan.action_type == DesktopActionType.CREATE_CODE_PROJECT:
            template = safe_plan.metadata.get("template_type", "web")
            pname = safe_plan.target_name or "MyProject"
            res = CodeProjectManager.create_project(pname, template_type=template, custom_files=safe_plan.file_names, open_in_vscode=True)
            if res.success and res.target_path:
                self.context_mgr.set_active_project(Path(res.target_path))
            return res

        # 12. WRITE DOCUMENT
        if safe_plan.action_type == DesktopActionType.WRITE_DOCUMENT:
            topic = safe_plan.content_topic or "Leave Application"
            fname = safe_plan.file_names[0] if safe_plan.file_names else "document.txt"
            res = DocumentEditor.write_and_open_document(topic, filename=fname)
            if res.success and res.target_path:
                self.context_mgr.register_created_files([Path(res.target_path)])
            return res

        # 13. OPEN CAMERA
        if safe_plan.action_type == DesktopActionType.OPEN_CAMERA:
            return self.camera_mgr.open_camera()

        # 14. TAKE PHOTO
        if safe_plan.action_type == DesktopActionType.TAKE_PHOTO:
            res = self.camera_mgr.capture_photo()
            if res.success and res.target_path:
                self.context_mgr.register_captured_photo(Path(res.target_path))
            return res

        return DesktopResult(success=False, action_type=safe_plan.action_type, error="Unhandled action type")

    def stop_active_task(self) -> bool:
        """Interrupt and cancel any running multi-step desktop task."""
        self._stop_requested.set()
        self._publish_event(NovaEvent.DESKTOP_ACTION_CANCELLED, action="stop_active_task")
        return True

    def shutdown(self) -> None:
        """Tear down desktop context and resources."""
        with self._lock:
            self.stop_active_task()
            self.context_mgr.reset()
            self._is_initialized = False
            logger.info("DesktopActionManager shut down.")
