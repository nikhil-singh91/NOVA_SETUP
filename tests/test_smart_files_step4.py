"""Step 4: Smart File & Folder Control Test Suite.

Verifies natural language search, opening, creation at requested locations
(Desktop, Documents, Downloads, parent folders), multi-file creation,
project scaffolding, renaming, safe deletion with confirmation, and multi-step tasks.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from desktop.files import FileSystemManager
from desktop.manager import DesktopActionManager
from desktop.models import DesktopActionType
from intent.engine import NaturalLanguageIntentEngine
from intent.models import CanonicalIntent


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create isolated test workspace."""
    ws = tmp_path / "test_env"
    ws.mkdir(parents=True, exist_ok=True)
    return ws


@pytest.fixture
def desktop_mgr() -> DesktopActionManager:
    return DesktopActionManager()


@pytest.fixture
def intent_engine() -> NaturalLanguageIntentEngine:
    return NaturalLanguageIntentEngine()


# =============================================================================
# 1. SEARCH & DISAMBIGUATION
# =============================================================================
def test_find_and_open_folder(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    dsa_dir = tmp_path / "DSA"
    dsa_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path]):
        with patch("subprocess.run") as mock_open:
            res = desktop_mgr.process_input("Open my DSA folder")
            assert res is not None
            assert res.success is True
            assert res.action_type == DesktopActionType.OPEN_FOLDER
            assert "DSA" in res.spoken_response
            mock_open.assert_called_once()


def test_find_multiple_matches_disambiguation(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    dsa1 = tmp_path / "Desktop" / "DSA"
    dsa2 = tmp_path / "Documents" / "DSA"
    dsa1.mkdir(parents=True, exist_ok=True)
    dsa2.mkdir(parents=True, exist_ok=True)

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Desktop", tmp_path / "Documents"]):
        res = desktop_mgr.process_input("Open my DSA folder")
        assert res is not None
        assert res.success is True
        assert "multiple folders named" in res.spoken_response
        assert len(res.metadata.get("multiple_matches", [])) == 2


def test_find_item_where_is(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    resume = tmp_path / "Documents" / "resume.pdf"
    resume.parent.mkdir(parents=True, exist_ok=True)
    resume.write_text("dummy resume")

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Documents"]):
        res = desktop_mgr.process_input("Where is my resume.pdf?")
        assert res is not None
        assert res.success is True
        assert "resume.pdf" in res.spoken_response


# =============================================================================
# 2. OPEN FILES IN APPLICATION
# =============================================================================
def test_open_file_in_vscode(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    cpp_file = tmp_path / "Desktop" / "a.cpp"
    cpp_file.parent.mkdir(parents=True, exist_ok=True)
    cpp_file.write_text("// test cpp")

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Desktop"]):
        with patch("desktop.apps.AppLauncher.launch", return_value=(True, "Opened", "Opened a.cpp in Visual Studio Code.")) as mock_launch:
            res = desktop_mgr.process_input("Open a.cpp in VS Code")
            assert res is not None
            assert res.success is True
            mock_launch.assert_called_once()


# =============================================================================
# 3. CREATE FOLDERS AT REQUESTED LOCATIONS
# =============================================================================
def test_create_folder_on_desktop(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(Path, "home", return_value=tmp_path):
        res = desktop_mgr.process_input("Create a folder called Test on Desktop")
        assert res is not None
        assert res.success is True
        created_path = Path(res.target_path)
        assert created_path.exists()
        assert created_path == desktop_dir / "Test"


def test_create_folder_in_documents(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    docs_dir = tmp_path / "Documents"
    docs_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(Path, "home", return_value=tmp_path):
        res = desktop_mgr.process_input("Make a directory called Practice in Documents")
        assert res is not None
        assert res.success is True
        created_path = Path(res.target_path)
        assert created_path.exists()
        assert created_path == docs_dir / "Practice"


def test_create_folder_inside_parent(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    dsa_dir = tmp_path / "Desktop" / "DSA"
    dsa_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Desktop"]):
        with patch.object(Path, "home", return_value=tmp_path):
            res = desktop_mgr.process_input("Create a folder called Trees inside my DSA folder")
            assert res is not None
            assert res.success is True
            created_path = Path(res.target_path)
            assert created_path.exists()
            assert created_path == dsa_dir / "Trees"


# =============================================================================
# 4. CREATE FILES
# =============================================================================
def test_create_file_on_desktop(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(Path, "home", return_value=tmp_path):
        res = desktop_mgr.process_input("Create a.cpp on Desktop")
        assert res is not None
        assert res.success is True
        created_path = Path(res.target_path)
        assert created_path.exists()
        assert created_path == desktop_dir / "a.cpp"


def test_create_multiple_files_inside_folder(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    test_dir = tmp_path / "Desktop" / "Test"
    test_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Desktop"]):
        with patch.object(Path, "home", return_value=tmp_path):
            res = desktop_mgr.process_input("Create index.html, style.css and app.js inside Test")
            assert res is not None
            assert res.success is True
            assert (test_dir / "index.html").exists()
            assert (test_dir / "style.css").exists()
            assert (test_dir / "app.js").exists()


def test_file_overwrite_protection(tmp_path: Path) -> None:
    target_file = tmp_path / "existing.txt"
    target_file.write_text("ORIGINAL CONTENT")

    success, paths, msg = FileSystemManager.create_files(
        ["existing.txt"],
        parent=tmp_path,
        content_map={"existing.txt": "NEW CONTENT"},
        overwrite=False,
    )
    assert success is True
    assert target_file.read_text() == "ORIGINAL CONTENT"


# =============================================================================
# 5. BASIC PROJECT STRUCTURES
# =============================================================================
def test_create_project_structure(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(Path, "home", return_value=tmp_path):
        res = desktop_mgr.process_input("Create a project called Demo on Desktop with index.html, style.css and app.js")
        assert res is not None
        assert res.success is True
        demo_dir = desktop_dir / "Demo"
        assert demo_dir.is_dir()
        assert (demo_dir / "index.html").is_file()
        assert (demo_dir / "style.css").is_file()
        assert (demo_dir / "app.js").is_file()


# =============================================================================
# 6. RENAME FILES AND FOLDERS
# =============================================================================
def test_rename_folder(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    test_dir = tmp_path / "Desktop" / "Test"
    test_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Desktop"]):
        res = desktop_mgr.process_input("Rename Test to TestProject")
        assert res is not None
        assert res.success is True
        assert not test_dir.exists()
        assert (tmp_path / "Desktop" / "TestProject").is_dir()


def test_rename_file(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    file_p = tmp_path / "Desktop" / "a.cpp"
    file_p.parent.mkdir(parents=True, exist_ok=True)
    file_p.write_text("int main() {}")

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Desktop"]):
        res = desktop_mgr.process_input("Rename a.cpp to tree.cpp")
        assert res is not None
        assert res.success is True
        assert not file_p.exists()
        assert (tmp_path / "Desktop" / "tree.cpp").is_file()


# =============================================================================
# 7. SAFE DELETE WITH CONFIRMATION
# =============================================================================
def test_safe_delete_confirmation_flow(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    folder_to_delete = tmp_path / "Desktop" / "TestProject"
    folder_to_delete.mkdir(parents=True, exist_ok=True)

    with patch.object(FileSystemManager, "get_safe_search_roots", return_value=[tmp_path / "Desktop"]):
        res = desktop_mgr.process_input("Delete TestProject")
        assert res is not None
        assert res.requires_confirmation is True
        assert "Do you want me to move it to Trash?" in res.spoken_response

        # Execute confirmed move to trash
        success, msg = FileSystemManager.safe_move_to_trash(folder_to_delete)
        assert success is True
        assert not folder_to_delete.exists()


# =============================================================================
# 8. MULTI-STEP FILE TASKS
# =============================================================================
def test_multi_step_file_task(tmp_path: Path, desktop_mgr: DesktopActionManager) -> None:
    desktop_dir = tmp_path / "Desktop"
    desktop_dir.mkdir(parents=True, exist_ok=True)

    with patch.object(Path, "home", return_value=tmp_path):
        with patch("desktop.apps.AppLauncher.launch", return_value=(True, "Opened", "Opened")) as mock_launch:
            res = desktop_mgr.process_input(
                "Create a folder called MyProject on Desktop, create a.cpp inside it, then open it in VS Code"
            )
            assert res is not None
            assert res.success is True
            proj_dir = desktop_dir / "MyProject"
            assert proj_dir.is_dir()
            assert (proj_dir / "a.cpp").is_file()
            mock_launch.assert_called_once()


# =============================================================================
# 9. NATURAL LANGUAGE VARIATIONS & INTENT NORMALIZATION
# =============================================================================
@pytest.mark.parametrize(
    "phrase,expected_intent",
    [
        ("NOVA, can you please make a new folder called Practice on my Desktop?", CanonicalIntent.CREATE_DESKTOP_FOLDER),
        ("Now create a.cpp inside Practice", CanonicalIntent.CREATE_DESKTOP_FILE),
        ("Find and open my Downloads folder", CanonicalIntent.OPEN_FOLDER),
        ("Where is my resume.pdf", CanonicalIntent.FIND_ITEM),
        ("Open a.cpp in VS Code", CanonicalIntent.OPEN_FILE),
        ("Rename Test to TestProject", CanonicalIntent.RENAME_ITEM),
        ("Delete TestProject", CanonicalIntent.DELETE_ITEM),
    ],
)
def test_step4_intent_matching_variations(
    intent_engine: NaturalLanguageIntentEngine, phrase: str, expected_intent: CanonicalIntent
) -> None:
    action = intent_engine.parse(phrase, allow_ai_fallback=False)
    assert action.intent == expected_intent
