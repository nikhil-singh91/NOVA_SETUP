"""Webpage readability extraction and content understanding for NOVA Browser Actions V2.1."""

from __future__ import annotations

import html
import re
import ssl
import urllib.parse
import urllib.request
from typing import Any

import certifi

from config.settings import settings
from core.logger import get_logger
from browser.engine import BaseBrowserEngine
from browser.models import PageContent, PageExtractionError

logger = get_logger(__name__)


class PageContentExtractor:
    """Extracts bounded, sanitized, readable text, headings, and links from an active browser tab."""

    def __init__(
        self,
        max_chars: int | None = None,
        max_links: int = 15,
        timeout_seconds: float | None = None,
    ) -> None:
        self.max_chars = max_chars or settings.browser_max_content_chars or 6000
        self.max_links = max_links
        self.timeout_seconds = (
            timeout_seconds or settings.browser_page_extract_timeout_seconds or 8.0
        )

    def _get_ssl_context(self) -> ssl.SSLContext:
        """Create a robust SSL context using certifi with fallback."""
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl._create_unverified_context()

    def extract_page(self, engine: BaseBrowserEngine) -> PageContent:
        """Extract clean readable content from the real active browser page."""
        page_info = engine.get_page_info()
        url = page_info.get("url", "").strip()
        title = page_info.get("title", "").strip()

        if not url or url.startswith("chrome://") or url.startswith("about:"):
            # If empty or internal URL, return basic metadata
            return PageContent(
                url=url or "about:blank",
                title=title or "New Tab",
                text=f"Title: {title or 'New Tab'}\nURL: {url or 'about:blank'}",
                headings=[title] if title else [],
            )

        # 1. Attempt AppleScript JavaScript extraction if supported
        extraction_js = f"""
        (function() {{
            try {{
                const maxChars = {self.max_chars};
                const docClone = document.body ? document.body.cloneNode(true) : document.documentElement.cloneNode(true);
                const selectorsToRemove = [
                    'script', 'style', 'noscript', 'iframe', 'svg', 'canvas',
                    'header', 'footer', 'nav', 'aside',
                    '[role="banner"]', '[role="navigation"]', '[role="complementary"]',
                    '.advertisement', '.ad-container', '.adsbygoogle',
                    '.cookie-banner', '#cookie-notice', '.cookie-consent'
                ];
                selectorsToRemove.forEach(sel => {{
                    docClone.querySelectorAll(sel).forEach(el => el.remove());
                }});

                const headings = [];
                docClone.querySelectorAll('h1, h2, h3').forEach(h => {{
                    const hText = h.innerText.trim();
                    if (hText && hText.length > 2 && !headings.includes(hText)) {{
                        headings.push(hText);
                    }}
                }});

                const articleEl = docClone.querySelector('article, main, [role="main"], #content, .content, .post');
                let rawText = articleEl ? articleEl.innerText : docClone.innerText;
                let cleanText = rawText.replace(/\\r\\n/g, '\\n').replace(/\\t/g, ' ').replace(/ +/g, ' ').trim();
                if (cleanText.length > maxChars) {{
                    cleanText = cleanText.substring(0, maxChars) + "...";
                }}

                return JSON.stringify({{
                    url: window.location.href,
                    title: document.title,
                    text: cleanText,
                    headings: headings.slice(0, 10)
                }});
            }} catch (e) {{
                return null;
            }}
        }})()
        """
        raw_result = engine.execute_script(extraction_js)
        if raw_result and isinstance(raw_result, (str, dict)):
            try:
                import json
                data = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
                if isinstance(data, dict) and data.get("text") and len(data["text"].strip()) > 5:
                    return PageContent(
                        url=data.get("url", url),
                        title=data.get("title", title),
                        text=data.get("text", ""),
                        headings=data.get("headings", []),
                        links=data.get("links", []),
                    )
            except Exception as e:
                logger.debug("Error parsing raw_result in extractor: %s", e)

        # 2. Reliable HTTP GET Readability Extraction Fallback
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, context=self._get_ssl_context(), timeout=self.timeout_seconds) as resp:
                raw_html = resp.read().decode("utf-8", errors="ignore")

                # Strip scripts and styles
                clean_html = re.sub(r"<script.*?</script>", "", raw_html, flags=re.DOTALL | re.IGNORECASE)
                clean_html = re.sub(r"<style.*?</style>", "", clean_html, flags=re.DOTALL | re.IGNORECASE)
                clean_html = re.sub(r"<nav.*?</nav>", "", clean_html, flags=re.DOTALL | re.IGNORECASE)
                clean_html = re.sub(r"<header.*?</header>", "", clean_html, flags=re.DOTALL | re.IGNORECASE)
                clean_html = re.sub(r"<footer.*?</footer>", "", clean_html, flags=re.DOTALL | re.IGNORECASE)

                # Extract headings
                heading_matches = re.findall(r"<h[1-3][^>]*>(.*?)</h[1-3]>", clean_html, flags=re.DOTALL | re.IGNORECASE)
                clean_headings = []
                for h in heading_matches:
                    text_h = re.sub(r"<[^>]+>", "", h).strip()
                    if text_h and text_h not in clean_headings:
                        clean_headings.append(text_h)

                # Extract paragraph content
                paragraphs = re.findall(r"<p[^>]*>(.*?)</p>", clean_html, flags=re.DOTALL | re.IGNORECASE)
                clean_paragraphs = [html.unescape(re.sub(r"<[^>]+>", "", p).strip()) for p in paragraphs if len(p.strip()) > 15]

                if clean_paragraphs:
                    body_text = "\n\n".join(clean_paragraphs)[: self.max_chars]
                else:
                    text_only = re.sub(r"<[^>]+>", " ", clean_html)
                    body_text = html.unescape(re.sub(r"\s+", " ", text_only)).strip()[: self.max_chars]

                return PageContent(
                    url=url,
                    title=title,
                    text=body_text,
                    headings=clean_headings[:10],
                )
        except Exception as exc:
            logger.debug("HTTP extraction fallback note for '%s': %s", url, exc)

        # 3. Fallback
        return PageContent(
            url=url,
            title=title,
            text=f"Webpage: {title}\nURL: {url}",
            headings=[title] if title else [],
        )

    def extract_search_results(
        self,
        engine: BaseBrowserEngine,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        """Extract structured organic search result items from search page or via search engine resolver."""
        page_info = engine.get_page_info()
        url = page_info.get("url", "")

        # 1. If currently on a Google search URL, parse results
        if "google.com/search" in url:
            query = ""
            parsed = urllib.parse.urlparse(url)
            params = urllib.parse.parse_qs(parsed.query)
            if "q" in params and params["q"]:
                query = params["q"][0]
            if query:
                return self.search_query_links(query, limit=limit)

        # 2. General HTTP Search Engine Resolver
        return []

    def search_query_links(self, query: str, limit: int = 5) -> list[dict[str, str]]:
        """Search query and return top organic titles and URLs."""
        try:
            data = urllib.parse.urlencode({"q": query}).encode("utf-8")
            req = urllib.request.Request(
                "https://html.duckduckgo.com/html/",
                data=data,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, context=self._get_ssl_context(), timeout=5.0) as resp:
                html_txt = resp.read().decode("utf-8", errors="ignore")
                results: list[dict[str, str]] = []

                for match in re.finditer(r'<a[^>]+class="result__url"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html_txt, re.DOTALL):
                    raw_url = match.group(1).strip()
                    clean_t = re.sub(r"<[^>]+>", "", match.group(2)).strip()
                    if "uddg=" in raw_url:
                        target_url = urllib.parse.unquote(raw_url.split("uddg=")[1].split("&")[0])
                    else:
                        target_url = raw_url
                    if target_url.startswith("http") and not any(b in target_url for b in ["duckduckgo.com", "adclick"]):
                        if not any(r["url"] == target_url for r in results):
                            results.append({"title": clean_t or target_url, "url": target_url, "snippet": ""})
                            if len(results) >= limit:
                                break
                return results
        except Exception as exc:
            logger.debug("search_query_links error: %s", exc)
            return []
