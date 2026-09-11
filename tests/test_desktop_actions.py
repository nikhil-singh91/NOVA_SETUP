"""Comprehensive unit and integration test suite for NOVA Desktop Actions V1."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch
import pytest

from desktop.apps import AppLauncher
from desktop.camera import CameraManager
from desktop.code import CodeProjectManager
from desktop.context import DesktopContextManager
from desktop.editor import DocumentEditor
from desktop.files import FileSystemManager
from desktop.manager import DesktopActionManager
from desktop.models import (
    DesktopActionPlan,
    DesktopActionType,
    DesktopResult,
    DesktopStep,
    DesktopTaskPlan,
)
from desktop.parser import DesktopIntentParser
from desktop.planner import DesktopTaskPlanner
from desktop.safety import DesktopSafetyPolicy


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "test_workspace"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


# ==============================================================================
# TEST 1: Application Discovery & Alias Resolution
# ==============================================================================

def test_app_alias_resolution() -> None:
    assert AppLauncher.resolve_app_name("vs code") == "Visual Studio Code"
    assert AppLauncher.resolve_app_name("notepad") == "TextEdit"
    assert AppLauncher.resolve_app_name("camera") == "Photo Booth"
    assert AppLauncher.resolve_app_name("terminal") == "Terminal"
    assert AppLauncher.resolve_app_name("finder") == "Finder"
    assert AppLauncher.resolve_app_name("spotify") == "Spotify"


def test_app_discovery_system_apps() -> None:
    textedit = AppLauncher.find_installed_app("TextEdit")
    assert textedit is not None
    assert textedit.exists()

    finder = AppLauncher.find_installed_app("Finder")
    assert finder is not None
    assert finder.exists()


# ==============================================================================
# TEST 2: Safe Folder & File Creation
# ==============================================================================

def test_create_folder(temp_workspace: Path) -> None:
    success, path, msg = FileSystemManager.create_folder("DSA", parent=temp_workspace)
    assert success is True
    assert path.exists()
    assert path.is_dir()
    assert path.name == "DSA"


def test_create_multiple_files_and_overwrite_guard(temp_workspace: Path) -> None:
    files = ["a.cpp", "b.cpp", "c.cpp"]
    success, paths, msg = FileSystemManager.create_files(files, parent=temp_workspace)
    assert success is True
    assert len(paths) == 3
    for p in paths:
        assert p.exists()

    # Non-destructive second write without overwrite
    success2, paths2, _ = FileSystemManager.create_files(["a.cpp"], parent=temp_workspace, overwrite=False)
    assert success2 is True
    assert paths2[0].exists()


def test_create_nested_tree(temp_workspace: Path) -> None:
    subfolders = ["Arrays", "LinkedList", "Trees"]
    success, root, all_paths, msg = FileSystemManager.create_tree("DSA", subfolders, parent=temp_workspace)
    assert success is True
    assert root.exists()
    assert (root / "Arrays").is_dir()
    assert (root / "LinkedList").is_dir()
    assert (root / "Trees").is_dir()


# ==============================================================================
# TEST 3: Code Scaffolding & Web Project Creation
# ==============================================================================

def test_create_web_project(temp_workspace: Path) -> None:
    res = CodeProjectManager.create_project("MyPortfolio", template_type="web", open_in_vscode=False, parent_dir=temp_workspace)
    assert res.success is True
    proj_dir = temp_workspace / "MyPortfolio"
    assert (proj_dir / "index.html").exists()
    assert (proj_dir / "style.css").exists()
    assert (proj_dir / "app.js").exists()

    html_txt = (proj_dir / "index.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_txt


def test_create_python_code_generation(temp_workspace: Path) -> None:
    code = CodeProjectManager.generate_code_content("calculator", language="python")
    assert "def add" in code or "def main" in code or "calculator" in code.lower()


# ==============================================================================
# TEST 4: Document Writing & Text Generation
# ==============================================================================

def test_document_writing(temp_workspace: Path) -> None:
    res = DocumentEditor.write_and_open_document("leave application", filename="leave_app.txt", parent_dir=temp_workspace, open_in_editor=False)
    assert res.success is True
    doc_path = temp_workspace / "leave_app.txt"
    assert doc_path.exists()
    content = doc_path.read_text(encoding="utf-8")
    assert "Leave" in content or "Application" in content


# ==============================================================================
# TEST 5: Desktop Intent Parsing
# ==============================================================================

def test_desktop_parser_apps() -> None:
    plan = DesktopIntentParser.parse("Open TextEdit")
    assert isinstance(plan, DesktopActionPlan)
    assert plan.action_type == DesktopActionType.OPEN_APP
    assert "textedit" in plan.app_name.lower()

    plan_close = DesktopIntentParser.parse("Close VS Code")
    assert isinstance(plan_close, DesktopActionPlan)
    assert plan_close.action_type == DesktopActionType.CLOSE_APP


def test_desktop_parser_files_and_folders() -> None:
    plan_folder = DesktopIntentParser.parse("Create a folder called DSA")
    assert isinstance(plan_folder, DesktopActionPlan)
    assert plan_folder.action_type == DesktopActionType.CREATE_FOLDER
    assert plan_folder.target_name.lower() == "dsa"

    plan_files = DesktopIntentParser.parse("Create files a.cpp b.cpp c.cpp")
    assert isinstance(plan_files, DesktopActionPlan)
    assert plan_files.action_type == DesktopActionType.CREATE_FILES
    assert plan_files.file_names == ["a.cpp", "b.cpp", "c.cpp"]


def test_desktop_parser_tree_multi_step() -> None:
    plan_tree = DesktopIntentParser.parse("Create a DSA folder with Arrays, LinkedList and Trees")
    assert isinstance(plan_tree, DesktopTaskPlan)
    assert len(plan_tree.steps) == 4  # Root + 3 subfolders


def test_desktop_parser_camera() -> None:
    plan_cam = DesktopIntentParser.parse("Take a picture")
    assert isinstance(plan_cam, DesktopActionPlan)
    assert plan_cam.action_type == DesktopActionType.TAKE_PHOTO

    plan_open_cam = DesktopIntentParser.parse("Open camera")
    assert isinstance(plan_open_cam, DesktopActionPlan)
    assert plan_open_cam.action_type == DesktopActionType.OPEN_CAMERA


# ==============================================================================
# TEST 6: Safety Boundaries & Workspace Protection
# ==============================================================================

def test_safety_boundary_protection() -> None:
    assert DesktopSafetyPolicy.is_safe_path(Path("/System")) is False
    assert DesktopSafetyPolicy.is_safe_path(Path("/Library")) is False
    assert DesktopSafetyPolicy.is_safe_path(Path("/usr/bin")) is False
    assert DesktopSafetyPolicy.is_safe_path(DesktopSafetyPolicy.get_default_workspace()) is True


# ==============================================================================
# TEST 7: DesktopActionManager Integration
# ==============================================================================

def test_desktop_manager_flow() -> None:
    manager = DesktopActionManager()
    manager.initialize()

    # 1. Folder creation
    res_f = manager.process_input("Create a folder called TestProject")
    assert res_f is not None
    assert res_f.success is True

    # 2. Files creation
    res_files = manager.process_input("Create files index.html style.css app.js")
    assert res_files is not None
    assert res_files.success is True

    # 3. Code creation
    res_code = manager.process_input("Create a Python file and write a calculator program")
    assert res_code is not None
    assert res_code.success is True

    # 4. Context tracking
    ctx = manager.context_mgr
    assert ctx.get_active_directory().exists()

    manager.shutdown()


def test_folder_search_and_trash_safety(tmp_path: Path) -> None:
    """Test folder search across safe paths and safe move to trash."""
    # 1. Folder creation
    dsa_dir = tmp_path / "DSA"
    dsa_dir.mkdir()
    file_to_delete = dsa_dir / "temp_file.txt"
    file_to_delete.write_text("temporary content")

    # 2. Trash safety
    success, msg = FileSystemManager.safe_move_to_trash(file_to_delete)
    assert success is True
    assert not file_to_delete.exists()

    # 3. Folder search
    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path]):
        matches = FileSystemManager.find_folders_by_name("DSA")
        assert len(matches) == 1
        assert matches[0] == dsa_dir
