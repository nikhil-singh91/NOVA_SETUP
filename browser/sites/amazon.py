"""Amazon product search, details, and price understanding skill (read-only, no purchases)."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

from core.logger import get_logger
from browser.engine import BaseBrowserEngine
from browser.models import ActionType, BrowserActionPlan, BrowserResult, Platform
from browser.sessions import BrowserSessionManager
from browser.sites.base import BaseSiteSkill

logger = get_logger(__name__)


class AmazonSkill(BaseSiteSkill):
    """Automates Amazon search, product data extraction, and comparison (strictly read-only)."""

    @property
    def name(self) -> str:
        return "amazon_skill"

    def can_handle(self, plan: BrowserActionPlan) -> bool:
        if plan.platform == Platform.AMAZON:
            return True
        if plan.metadata.get("site_key") == "amazon":
            return True
        return False

    def execute(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
        sessions: BrowserSessionManager,
    ) -> BrowserResult:
        """Execute Amazon search or product extraction."""
        query = (plan.query or "").strip()

        if plan.action_type == ActionType.COMPARE_PRODUCTS:
            return self._handle_comparison(plan, engine)

        if not query:
            url = "https://www.amazon.in"
            engine.open_url(url)
            return BrowserResult(
                success=True,
                action_type=plan.action_type,
                message="Opened Amazon homepage.",
                spoken_response="Opening Amazon.",
                url=url,
            )

        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.amazon.in/s?k={encoded}"
        success = engine.open_url(search_url)

        if not success:
            return BrowserResult(
                success=False,
                action_type=plan.action_type,
                message=f"Failed to search Amazon for '{query}'.",
                spoken_response=f"Couldn't search Amazon for {query}.",
                url=search_url,
                error="Navigation failed",
            )

        # Extract top 3 product cards for immediate understanding
        extract_products_js = """
        (function() {
            const products = [];
            const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
            for (let card of cards) {
                const titleEl = card.querySelector('h2 a span, h2 span');
                const priceEl = card.querySelector('.a-price .a-offscreen, .a-price-whole');
                const ratingEl = card.querySelector('i.a-icon-star-small span, .a-icon-alt');
                const linkEl = card.querySelector('h2 a');
                if (titleEl && priceEl) {
                    products.push({
                        title: titleEl.innerText.trim(),
                        price: priceEl.innerText.trim(),
                        rating: ratingEl ? ratingEl.innerText.trim() : "N/A",
                        url: linkEl ? linkEl.href : ""
                    });
                    if (products.length >= 3) break;
                }
            }
            return JSON.stringify(products);
        })()
        """
        raw_prods = engine.execute_script(extract_products_js)
        products = []
        if raw_prods:
            try:
                products = json.loads(str(raw_prods))
            except Exception:
                pass

        if products:
            spoken_items = [f"{p['title'][:40]} at {p['price']}" for p in products[:2]]
            spoken = f"Found top Amazon products for '{query}': {', and '.join(spoken_items)}."
        else:
            spoken = f"Searching Amazon for '{query}'."

        return BrowserResult(
            success=True,
            action_type=plan.action_type,
            message=spoken,
            spoken_response=spoken,
            url=search_url,
            metadata={"products": products},
        )

    def _handle_comparison(
        self,
        plan: BrowserActionPlan,
        engine: BaseBrowserEngine,
    ) -> BrowserResult:
        """Extract top product details for side-by-side comparison."""
        extract_js = """
        (function() {
            const items = [];
            const cards = document.querySelectorAll('div[data-component-type="s-search-result"]');
            for (let card of cards) {
                const titleEl = card.querySelector('h2 span');
                const priceEl = card.querySelector('.a-price-whole');
                const ratingEl = card.querySelector('.a-icon-alt');
                if (titleEl && priceEl) {
                    items.push({
                        name: titleEl.innerText.trim(),
                        price: priceEl.innerText.trim(),
                        rating: ratingEl ? ratingEl.innerText.trim() : "N/A"
                    });
                    if (items.length >= 2) break;
                }
            }
            return JSON.stringify(items);
        })()
        """
        raw_items = engine.execute_script(extract_js)
        items = []
        if raw_items:
            try:
                items = json.loads(str(raw_items))
            except Exception:
                pass

        if len(items) >= 2:
            spoken = (
                f"Comparing top options: 1. {items[0]['name'][:35]} priced at ₹{items[0]['price']} ({items[0]['rating']}), "
                f"versus 2. {items[1]['name'][:35]} priced at ₹{items[1]['price']} ({items[1]['rating']})."
            )
        else:
            spoken = "I inspected the Amazon listings for comparison."

        return BrowserResult(
            success=True,
            action_type=plan.action_type,
            message=spoken,
            spoken_response=spoken,
            metadata={"comparison_items": items},
        )
