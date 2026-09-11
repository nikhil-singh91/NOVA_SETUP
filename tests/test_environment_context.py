"""Tests for Canonical EnvironmentContext, EnvironmentObserver, and ContextResolver."""

from __future__ import annotations

import os
from pathlib import Path
from core.environment import ContextResolver, EnvironmentContext, EnvironmentObserver


def test_environment_context_creation() -> None:
    """Validate EnvironmentContext properties and serialization."""
    ctx = EnvironmentContext(
        active_application="Google Chrome",
        active_window="Flipkart.com - Online Shopping",
        active_browser="Google Chrome",
        active_tab_index=2,
        active_tab_count=5,
        current_url="https://www.flipkart.com/search?q=mobile+phones",
        current_domain="flipkart.com",
        current_page_title="Mobile Phones - Buy Mobiles Online at Best Prices in India | Flipkart",
    )
    d = ctx.to_dict()
    assert d["active_application"] == "Google Chrome"
    assert d["current_domain"] == "flipkart.com"
    assert d["active_tab_index"] == 2
    assert d["has_pending_confirmation"] is False


def test_context_resolver_browser_here() -> None:
    """Validate 'here' and 'current page' resolution against real browser state."""
    ctx = EnvironmentContext(
        active_application="Google Chrome",
        current_url="https://www.flipkart.com",
        current_domain="flipkart.com",
        current_page_title="Online Shopping Site for Mobiles, Electronics, Furniture",
    )

    res_here = ContextResolver.resolve_target("here", ctx, target_type="site")
    assert res_here["resolved"] is True
    assert res_here["domain"] == "flipkart.com"
    assert res_here["site_key"] == "flipkart"
    assert res_here["source"] == "real_current_state"

    res_page = ContextResolver.resolve_target("this page", ctx, target_type="page")
    assert res_page["resolved"] is True
    assert res_page["domain"] == "flipkart.com"


def test_context_resolver_finder_selection(tmp_path: Path) -> None:
    """Validate 'this' and 'selected file' resolution against real Finder state."""
    test_file = tmp_path / "assignment.pdf"
    test_file.write_text("dummy assignment content")

    ctx = EnvironmentContext(
        active_application="Finder",
        selected_file_or_folder=test_file,
        selected_files=[test_file],
        current_folder=tmp_path,
    )

    res = ContextResolver.resolve_target("this", ctx, target_type="any")
    assert res["resolved"] is True
    assert res["target"] == test_file
    assert res["source"] == "real_current_state"
    assert res["type"] == "file"


def test_context_resolver_recent_nova_context(tmp_path: Path) -> None:
    """Validate 'it' and 'the folder I just created' resolution from recent NOVA context."""
    created_dir = tmp_path / "DSA"
    created_dir.mkdir()

    ctx = EnvironmentContext(
        active_application="Terminal",
        last_created_path=created_dir,
    )

    res = ContextResolver.resolve_target("it", ctx, target_type="folder")
    assert res["resolved"] is True
    assert res["target"] == created_dir
    assert res["source"] == "recent_nova_context"
    assert res["type"] == "directory"


def test_context_resolver_priority_hierarchy(tmp_path: Path) -> None:
    """Validate that real current state takes priority over stale recent memory."""
    # Stale recent memory: previous folder created yesterday
    stale_folder = tmp_path / "StaleFolder"
    stale_folder.mkdir()

    # Real active state: user currently selected assignment.pdf in Finder
    real_selected = tmp_path / "current_assignment.pdf"
    real_selected.write_text("current active file")

    ctx = EnvironmentContext(
        active_application="Finder",
        selected_file_or_folder=real_selected,
        selected_files=[real_selected],
        current_folder=tmp_path,
        last_created_path=stale_folder,  # Stale memory
    )

    res = ContextResolver.resolve_target("this", ctx, target_type="any")
    assert res["resolved"] is True
    # Real current state must win over stale memory!
    assert res["target"] == real_selected
    assert res["source"] == "real_current_state"
