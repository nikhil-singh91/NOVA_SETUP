"""Collects structured real video candidates from YouTube search results."""

from __future__ import annotations

import json
import re
import ssl
import urllib.parse
import urllib.request

import certifi
from core.logger import get_logger

from media.models import VideoCandidate

logger = get_logger(__name__)


def parse_duration_to_seconds(dur_str: str) -> int:
    """Convert YouTube duration string (e.g. '2:53', '1:09:21', '0:08') into integer seconds."""
    if not dur_str:
        return 0
    clean = dur_str.strip()
    parts = clean.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1:
            return int(parts[0])
    except ValueError:
        return 0
    return 0


class YouTubeCandidateCollector:
    """Collects structured, parsed video result items from YouTube search endpoints."""

    def __init__(self, timeout_seconds: float = 5.0) -> None:
        self.timeout_seconds = timeout_seconds

    def _get_ssl_context(self) -> ssl.SSLContext:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            return ssl._create_unverified_context()

    def collect_candidates(self, query: str, limit: int = 10) -> list[VideoCandidate]:
        """Fetch YouTube search HTML and extract structured video cards from ytInitialData."""
        encoded = urllib.parse.quote_plus(query)
        search_url = f"https://www.youtube.com/results?search_query={encoded}"
        candidates: list[VideoCandidate] = []

        try:
            req = urllib.request.Request(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                },
            )
            with urllib.request.urlopen(req, context=self._get_ssl_context(), timeout=self.timeout_seconds) as resp:
                html_txt = resp.read().decode("utf-8", errors="ignore")

                # Extract ytInitialData JSON
                m = re.search(r"var ytInitialData\s*=\s*({.+?});</script>", html_txt)
                if not m:
                    m = re.search(r"ytInitialData\s*=\s*({.+?});", html_txt)

                if m:
                    try:
                        data = json.loads(m.group(1))
                        contents = (
                            data.get("contents", {})
                            .get("twoColumnSearchResultsRenderer", {})
                            .get("primaryContents", {})
                            .get("sectionListRenderer", {})
                            .get("contents", [])
                        )

                        for section in contents:
                            items = section.get("itemSectionRenderer", {}).get("contents", [])
                            for item in items:
                                if "videoRenderer" in item:
                                    vr = item["videoRenderer"]
                                    vid_id = vr.get("videoId")
                                    if not vid_id:
                                        continue

                                    # Extract title
                                    title = "".join(
                                        [r.get("text", "") for r in vr.get("title", {}).get("runs", [])]
                                    ).strip()
                                    if not title and "simpleText" in vr.get("title", {}):
                                        title = vr["title"]["simpleText"]

                                    # Extract channel
                                    channel = "".join(
                                        [r.get("text", "") for r in vr.get("ownerText", {}).get("runs", [])]
                                    ).strip()

                                    # Extract duration
                                    dur_str = vr.get("lengthText", {}).get("simpleText", "")
                                    dur_secs = parse_duration_to_seconds(dur_str)

                                    # Extract badges
                                    badges = []
                                    for b in vr.get("badges", []):
                                        label = b.get("metadataBadgeRenderer", {}).get("label", "")
                                        if label:
                                            badges.append(label)
                                    for b in vr.get("ownerBadges", []):
                                        label = b.get("metadataBadgeRenderer", {}).get("tooltip", "")
                                        if label:
                                            badges.append(label)

                                    is_short = (dur_secs > 0 and dur_secs <= 60) or "#shorts" in title.lower()
                                    is_live = "LIVE" in dur_str or any("live" in b.lower() for b in badges)

                                    candidate = VideoCandidate(
                                        video_id=vid_id,
                                        title=title,
                                        channel=channel,
                                        duration_str=dur_str,
                                        duration_seconds=dur_secs,
                                        url=f"https://www.youtube.com/watch?v={vid_id}",
                                        badges=badges,
                                        position=len(candidates) + 1,
                                        is_short=is_short,
                                        is_live=is_live,
                                    )
                                    candidates.append(candidate)
                                    if len(candidates) >= limit:
                                        break
                    except Exception as e:
                        logger.debug("Failed to parse ytInitialData: %s", e)

        except Exception as exc:
            logger.debug("YouTube candidate collection error: %s", exc)

        return candidates
