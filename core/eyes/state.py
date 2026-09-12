"""Unified Computer State and Screen World Model for NOVA Eyes.

Maintains an in-memory, structured representation of the user's active computer
state including active application, window, browser tabs, URL, search queries,
interactive elements, focused targets, dialogs, product candidates, and errors.
Zero disk writes, strictly latest state in RAM.
"""

from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from core.eyes.accessibility import SemanticElement, UIElementType
from core.eyes.capture import DisplayMetrics
from core.eyes.vision_ocr import VisualEntityCard

try:
    import Quartz
    Quartz: Any = Quartz
except ImportError:
    Quartz = None


class PageCategory(str, Enum):
    """Broad semantic classification of the current screen content."""

    SHOPPING = "shopping"
    CODING = "coding"
    DOCUMENTATION = "documentation"
    VIDEO = "video"
    SOCIAL = "social"
    EMAIL = "email"
    SEARCH_RESULTS = "search_results"
    SETTINGS = "settings"
    TERMINAL = "terminal"
    PDF = "pdf"
    AUTH_LOGIN = "auth_login"
    GENERAL = "general"


@dataclass
class ProductCandidate:
    """A detected commercial product or listing candidate on screen."""

    title: str
    price: str = ""
    price_val: float = 0.0
    rating: str = ""
    rating_val: float = 0.0
    specs: list[str] = field(default_factory=list)
    center_point: tuple[float, float] = (0.0, 0.0)
    bounding_box: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)

    @classmethod
    def from_visual_card(cls, card: VisualEntityCard) -> ProductCandidate:
        return cls(
            title=card.title,
            price=card.price,
            price_val=card.price_val,
            rating=card.rating,
            rating_val=card.rating_val,
            specs=card.specs,
            center_point=card.center_point,
            bounding_box=card.bounding_box,
        )


@dataclass
class ScreenState:
    """Instantaneous world model of the computer state currently visible to NOVA Eyes."""

    timestamp: datetime
    active_application: str
    active_window: str
    metrics: DisplayMetrics
    visual_hash: str

    # Browser & Page Awareness
    active_browser: str = ""
    active_tab_index: int = 1
    active_tab_count: int = 1
    active_tab_title: str = ""
    current_url: str = ""
    current_domain: str = ""
    current_search_query: str = ""
    visible_tabs: list[str] = field(default_factory=list)

    # Semantic Categorization & Entities
    page_category: PageCategory = PageCategory.GENERAL
    product_candidates: list[ProductCandidate] = field(default_factory=list)
    contains_sensitive_data: bool = False

    # Pointer & Geometry
    cursor_position: tuple[float, float] = (0.0, 0.0)

    # UI Element Collections
    elements: list[SemanticElement] = field(default_factory=list)
    buttons: list[SemanticElement] = field(default_factory=list)
    inputs: list[SemanticElement] = field(default_factory=list)
    links: list[SemanticElement] = field(default_factory=list)
    tabs: list[SemanticElement] = field(default_factory=list)
    dialogs: list[SemanticElement] = field(default_factory=list)
    scroll_areas: list[SemanticElement] = field(default_factory=list)
    images: list[SemanticElement] = field(default_factory=list)

    # Text & Errors
    visible_texts: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    focused_element: SemanticElement | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.timestamp).total_seconds()

    def is_fresh(self, max_age_seconds: float = 3.0) -> bool:
        return self.age_seconds <= max_age_seconds

    def has_changed_from(self, previous: ScreenState | None) -> bool:
        """Determine whether the screen has experienced a meaningful change."""
        if previous is None:
            return True

        if self.active_application != previous.active_application:
            return True
        if self.active_window != previous.active_window:
            return True
        if self.current_url and previous.current_url and self.current_url != previous.current_url:
            return True
        if self.visual_hash and previous.visual_hash and self.visual_hash != previous.visual_hash:
            return True
        if abs(len(self.elements) - len(previous.elements)) > 2:
            return True

        return False

    def find_elements_by_label(
        self,
        label: str,
        element_type: UIElementType | None = None,
    ) -> list[SemanticElement]:
        """Search detected elements by label substring and optional type."""
        norm_label = label.lower().strip()
        matches: list[SemanticElement] = []
        for elem in self.elements:
            if element_type and elem.element_type != element_type:
                continue
            if norm_label in elem.label.lower() or norm_label in elem.value.lower():
                matches.append(elem)
        return matches

    def get_element_under_cursor(self) -> SemanticElement | None:
        """Return the innermost semantic UI element directly under the current pointer position."""
        cx, cy = self.cursor_position
        candidates: list[SemanticElement] = []
        for e in self.elements:
            ex, ey, ew, eh = e.bounding_box
            if ex <= cx <= (ex + ew) and ey <= cy <= (ey + eh):
                candidates.append(e)

        if not candidates:
            return None
        # Sort by smallest bounding box area (innermost element)
        candidates.sort(key=lambda elem: elem.width * elem.height)
        return candidates[0]

    # =========================================================================
    # NATURAL SUMMARIZATION AND CONTENT UNDERSTANDING
    # =========================================================================

    def get_natural_screen_description(self, is_hinglish: bool = False) -> str:
        """Produce a natural, human-friendly conversational description of the current screen."""
        app = (self.active_application or "Desktop").strip()
        win = (self.active_window or "").strip()

        # 1. Error state takes priority if present
        if self.errors:
            err = self.errors[0]
            if len(err) > 100:
                err = err[:97] + "..."
            if is_hinglish:
                return f"Screen par ek error dikh raha hai: '{err}'."
            return f"There's an error on your screen: '{err}'."

        app_lower = app.lower()
        win_lower = win.lower()

        # 2. Shopping Page
        if self.page_category == PageCategory.SHOPPING:
            candidates_cnt = len(self.product_candidates)
            if candidates_cnt > 1:
                p_names = [p.title for p in self.product_candidates[:2]]
                names_str = " aur ".join(f"'{n}'" for n in p_names) if is_hinglish else " and ".join(f"'{n}'" for n in p_names)
                if is_hinglish:
                    return f"Aap ek shopping page par ho jahan {candidates_cnt} products dikh rahe hain, jaise {names_str}."
                return f"You're browsing a shopping page with {candidates_cnt} products visible, including {names_str}."
            elif candidates_cnt == 1:
                p = self.product_candidates[0]
                price_str = f" ({p.price})" if p.price else ""
                if is_hinglish:
                    return f"Aap '{p.title}'{price_str} dekh rahe ho."
                return f"You're looking at '{p.title}'{price_str}."

        # 3. Browser detection
        if self.active_browser or any(b in app_lower for b in ("chrome", "safari", "brave", "edge", "firefox", "browser")):
            # Search results
            if self.current_search_query:
                q = self.current_search_query
                if is_hinglish:
                    return f"Aap browser mein '{q}' ke search results dekh rahe ho."
                return f"You're in your browser looking at search results for '{q}'."

            # Video / YouTube
            if "youtube" in win_lower or any("youtube" in t.lower() for t in self.visible_texts[:5]):
                if "/shorts" in win_lower or "shorts" in win_lower:
                    return "Aap abhi YouTube Shorts dekh rahe ho." if is_hinglish else "You're on YouTube Shorts right now."
                title_candidates = [
                    t for t in self.visible_texts
                    if len(t) > 10 and not any(k in t.lower() for k in ("youtube", "subscribers", "views", "share", "save", "download", "home", "explore", "subscribe", "notification"))
                ]
                if title_candidates:
                    vid_title = title_candidates[0]
                    return f"Aap abhi YouTube par '{vid_title}' dekh rahe ho." if is_hinglish else f"You're on YouTube right now, looking at '{vid_title}'."
                clean_win = win.replace(" - YouTube", "").strip()
                return f"Aap abhi YouTube par '{clean_win}' par ho." if is_hinglish else f"You're on YouTube right now looking at '{clean_win}'."

            clean_win = win.split(" - ")[0].strip() if " - " in win else win
            if clean_win:
                return f"Aap browser mein '{clean_win}' dekh rahe ho." if is_hinglish else f"You're in your browser looking at '{clean_win}'."
            return "Aap abhi browser use kar rahe ho." if is_hinglish else "You're currently in your browser."

        # 4. Code Editor / Terminal
        if any(ide in app_lower for ide in ("code", "cursor", "sublime", "pycharm", "intellij", "terminal", "iterm", "xcode")):
            clean_win = win.split(" — ")[0].split(" - ")[0].strip() if win else app
            return f"Aap {app} mein ho, aur '{clean_win}' open hai." if is_hinglish else f"You're in {app}, working on '{clean_win}'."

        # 5. Finder / Files
        if "finder" in app_lower:
            return f"Aap Finder mein '{win}' folder dekh rahe ho." if is_hinglish else f"You're in Finder looking at the '{win}' folder."

        # 6. General
        if win and win.lower() != app_lower:
            return f"Aap abhi {app} mein '{win}' dekh rahe ho." if is_hinglish else f"You're currently in {app}, looking at '{win}'."
        return f"Aap abhi {app} dekh rahe ho." if is_hinglish else f"You're currently looking at {app}."

    def summarize_page(self, is_hinglish: bool = False) -> str:
        """Provide a structured summary of the currently observed page."""
        app = self.active_application or "Desktop"
        win = self.active_window or "Screen"

        # Shopping summary
        if self.page_category == PageCategory.SHOPPING and self.product_candidates:
            items_desc = []
            for p in self.product_candidates[:4]:
                p_info = p.title
                if p.price:
                    p_info += f" - {p.price}"
                if p.rating:
                    p_info += f" ({p.rating})"
                items_desc.append(p_info)

            items_joined = "; ".join(items_desc)
            if is_hinglish:
                return f"Aap ek product listing page par ho. Visible options hain: {items_joined}."
            return f"You are on a product listing page. Currently visible items include: {items_joined}."

        # Search summary
        if self.current_search_query:
            return (
                f"Aap '{self.current_search_query}' ke search results dekh rahe ho."
                if is_hinglish
                else f"You are looking at search results for '{self.current_search_query}'."
            )

        # General text summary from visible texts
        meaningful_texts = [
            t for t in self.visible_texts
            if len(t) > 15 and not any(k in t.lower() for k in ("cookie", "privacy", "terms", "sign in", "login"))
        ]
        snippet = " ".join(meaningful_texts[:3]) if meaningful_texts else win
        if len(snippet) > 220:
            snippet = snippet[:217] + "..."

        if is_hinglish:
            return f"Current page: '{win}' in {app}. Main visible content: {snippet}"
        return f"Current page: '{win}' in {app}. Key visible content: {snippet}"

    def compare_visible_products(self, is_hinglish: bool = False) -> str:
        """Compare visible product candidates on screen."""
        if not self.product_candidates or len(self.product_candidates) < 2:
            return (
                "Screen par comparison ke liye multiple products clear nahi hain."
                if is_hinglish
                else "I can't clearly see multiple product candidates on screen to compare."
            )

        p1 = self.product_candidates[0]
        p2 = self.product_candidates[1]

        c1 = f"{p1.title} ({p1.price or 'Price not visible'}" + (f", {p1.rating}" if p1.rating else "") + ")"
        c2 = f"{p2.title} ({p2.price or 'Price not visible'}" + (f", {p2.rating}" if p2.rating else "") + ")"

        if is_hinglish:
            return f"Visible options compare kar raha hoon: Pehla hai {c1}, aur doosra hai {c2}."
        return f"Comparing visible options: First is {c1}, and second is {c2}."

    # =========================================================================
    # STATE BUILDER FROM SOURCES
    # =========================================================================

    @classmethod
    def build_from_sources(
        cls,
        timestamp: datetime,
        active_app: str,
        active_win: str,
        metrics: DisplayMetrics,
        visual_hash: str,
        ax_elements: list[SemanticElement],
        ocr_elements: list[SemanticElement],
        visual_cards: list[VisualEntityCard] | None = None,
        browser_info: dict[str, Any] | None = None,
    ) -> ScreenState:
        """Fuse Accessibility elements, Vision OCR, and browser context into a unified ComputerState."""
        all_elements: list[SemanticElement] = list(ax_elements)
        existing_centers = [e.center_point for e in ax_elements]

        # Merge OCR elements if not closely overlapping an existing AX element
        for ocr_elem in ocr_elements:
            ox, oy = ocr_elem.center_point
            is_duplicate = False
            for ex, ey in existing_centers:
                if abs(ox - ex) < 25 and abs(oy - ey) < 20:
                    is_duplicate = True
                    break

            if not is_duplicate:
                all_elements.append(ocr_elem)
                existing_centers.append((ox, oy))

        buttons = [e for e in all_elements if e.element_type in (UIElementType.BUTTON, UIElementType.MENU_ITEM)]
        inputs = [e for e in all_elements if e.is_input or e.element_type == UIElementType.INPUT]
        links = [e for e in all_elements if e.element_type == UIElementType.LINK]
        tabs = [e for e in all_elements if e.element_type == UIElementType.TAB]
        dialogs = [e for e in all_elements if e.element_type in (UIElementType.DIALOG, UIElementType.POPUP)]
        scroll_areas = [e for e in all_elements if e.is_scrollable]
        images = [e for e in all_elements if e.element_type == UIElementType.IMAGE]

        focused = next((e for e in all_elements if e.is_focused), None)

        # Detect sensitive data presence
        has_sensitive = any(e.is_sensitive for e in all_elements)

        # Query pointer cursor position
        cursor_pos = (0.0, 0.0)
        if Quartz and hasattr(Quartz, "CGEventGetLocation"):
            try:
                ev = Quartz.CGEventCreate(None)
                if ev:
                    pt = Quartz.CGEventGetLocation(ev)
                    cursor_pos = (float(pt.x), float(pt.y))
            except Exception:
                pass

        # Extract sorted unique visible text lines
        sorted_texts = sorted(
            [e.label.strip() for e in all_elements if e.label.strip()],
            key=lambda s: len(s),
            reverse=True,
        )
        unique_texts: list[str] = []
        for t in sorted_texts:
            if t not in unique_texts and len(t) > 1:
                unique_texts.append(t)

        # Detect error patterns
        err_keywords = [
            "error", "fatal", "exception", "failed", "traceback", "cannot find", "access denied", "404 not found"
        ]
        errors: list[str] = []
        for t in unique_texts:
            t_low = t.lower()
            if any(k in t_low for k in err_keywords) and len(t) > 4:
                errors.append(t)

        # Browser info integration
        b_info = browser_info or {}
        active_b = b_info.get("active_browser", "")
        tab_idx = b_info.get("active_tab_index", 1)
        tab_cnt = b_info.get("active_tab_count", 1)
        tab_title = b_info.get("current_page_title", "")
        url = b_info.get("current_url", "")
        domain = b_info.get("current_domain", "")
        vis_tabs = b_info.get("visible_tabs", [])

        # Extract search query from URL or search input
        search_query = ""
        if url:
            try:
                parsed = urllib.parse.urlparse(url)
                qs = urllib.parse.parse_qs(parsed.query)
                for q_key in ("q", "query", "search", "k", "field-keywords", "keywords"):
                    if q_key in qs and qs[q_key]:
                        search_query = qs[q_key][0].strip()
                        break
            except Exception:
                pass

        if not search_query:
            # Check if search input has a value
            search_fields = [i for i in inputs if "search" in i.label.lower() or "search" in i.role.lower()]
            if search_fields and search_fields[0].value:
                search_query = search_fields[0].value

        # Classify Page Category
        cat = PageCategory.GENERAL
        combined_text = f"{active_app} {active_win} {domain} {' '.join(unique_texts[:10])}".lower()

        if any(w in combined_text for w in ("cart", "checkout", "price", "buy now", "rating", "products", "shoes", "deals", "store", "amazon", "flipkart")):
            cat = PageCategory.SHOPPING
        elif search_query or "search results" in combined_text:
            cat = PageCategory.SEARCH_RESULTS
        elif any(w in combined_text for w in ("youtube", "video", "shorts", "vimeo", "netflix", "spotify")):
            cat = PageCategory.VIDEO
        elif any(w in combined_text for w in ("terminal", "bash", "zsh", "iterm", "fish")):
            cat = PageCategory.TERMINAL
        elif any(w in combined_text for w in ("github", "gitlab", "vscode", "pycharm", "cursor", "sublime", "xcode")):
            cat = PageCategory.CODING
        elif any(w in combined_text for w in ("docs", "documentation", "api reference", "manual", "guide")):
            cat = PageCategory.DOCUMENTATION
        elif any(w in combined_text for w in ("password", "sign in", "login", "authenticate")):
            cat = PageCategory.AUTH_LOGIN

        # Build Product Candidates from visual cards
        product_cands: list[ProductCandidate] = []
        if visual_cards:
            product_cands = [ProductCandidate.from_visual_card(c) for c in visual_cards]

        return cls(
            timestamp=timestamp,
            active_application=active_app,
            active_window=active_win,
            metrics=metrics,
            visual_hash=visual_hash,
            active_browser=active_b,
            active_tab_index=tab_idx,
            active_tab_count=tab_cnt,
            active_tab_title=tab_title,
            current_url=url,
            current_domain=domain,
            current_search_query=search_query,
            visible_tabs=vis_tabs,
            page_category=cat,
            product_candidates=product_cands,
            contains_sensitive_data=has_sensitive,
            cursor_position=cursor_pos,
            elements=all_elements,
            buttons=buttons,
            inputs=inputs,
            links=links,
            tabs=tabs,
            dialogs=dialogs,
            scroll_areas=scroll_areas,
            images=images,
            visible_texts=unique_texts[:35],
            errors=errors,
            focused_element=focused,
        )
