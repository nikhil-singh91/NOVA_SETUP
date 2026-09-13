"""Real Anakin API Live Web Intelligence Service for NOVA.

Provides synchronous web search with citations and asynchronous deep multi-source
research, normalized into NOVA's internal models, integrated with the capability
registry and short-term task context.
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from config.settings import settings
from core.exceptions import AuthenticationError, NetworkError, NovaError, SearchError
from core.logger import get_logger

logger = get_logger(__name__)

# Apply compatibility fix for anakin-sdk v0.1.0 Pydantic model where structured_data
# from /v1/agentic-search can be returned as a list or dict.
try:
    import anakin.models
    anakin.models.AgenticSearchData.model_fields["structured_data"].annotation = (
        dict[str, Any] | list[Any] | None
    )
    anakin.models.AgenticSearchData.model_rebuild(force=True)
    anakin.models.AgenticSearchResult.model_rebuild(force=True)
except Exception as exc:  # pragma: no cover
    logger.debug("Anakin SDK model compatibility patch skipped: %s", exc)


class CapabilityStatus(str, Enum):
    """Truthful runtime status of a NOVA capability."""

    IMPLEMENTED = "IMPLEMENTED"
    AVAILABLE = "AVAILABLE"
    UNAVAILABLE = "UNAVAILABLE"
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    INSUFFICIENT_CREDITS = "INSUFFICIENT_CREDITS"
    RATE_LIMITED = "RATE_LIMITED"
    DEPENDENCY_MISSING = "DEPENDENCY_MISSING"
    CONFIGURATION_MISSING = "CONFIGURATION_MISSING"
    TEMPORARILY_FAILED = "TEMPORARILY_FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass
class CapabilityHealth:
    """Truthful self-knowledge report for the live web research capability."""

    capability_id: str = "live_web_research"
    name: str = "Live Web Intelligence (Anakin)"
    purpose: str = "Live web search and deep multi-source research for current world information"
    status: CapabilityStatus = CapabilityStatus.UNKNOWN
    is_available: bool = False
    required_dependency: str = "anakin-sdk"
    required_env_var: str = "ANAKIN_API_KEY"
    supported_operations: list[str] = field(
        default_factory=lambda: ["search_web", "agentic_research"]
    )
    limitations: str = "Requires valid internet connectivity and active Anakin credits."
    last_checked: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    details: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "purpose": self.purpose,
            "status": self.status.value,
            "is_available": self.is_available,
            "required_dependency": self.required_dependency,
            "required_env_var": self.required_env_var,
            "supported_operations": self.supported_operations,
            "limitations": self.limitations,
            "last_checked": self.last_checked,
            "details": self.details,
        }


# =============================================================================
# EXCEPTION HIERARCHY
# =============================================================================


class AnakinServiceError(SearchError):
    """Base exception for all Anakin service operations."""

    default_message = "Live web research operation failed."


class AnakinConfigurationError(AnakinServiceError):
    """Raised when ANAKIN_API_KEY is missing or invalid in configuration."""

    default_message = (
        "Live web research through Anakin is unavailable because configuration is missing."
    )


class AnakinAuthenticationError(AnakinServiceError, AuthenticationError):
    """Raised when authentication with Anakin fails (invalid or expired key)."""

    default_message = (
        "Live web research failed because the Anakin API key is invalid or expired."
    )


class AnakinInsufficientCreditsError(AnakinServiceError):
    """Raised when the Anakin account has insufficient credits."""

    default_message = (
        "Live web research unavailable because the Anakin account has insufficient credits."
    )


class AnakinRateLimitError(AnakinServiceError):
    """Raised when Anakin API rate limit is exceeded."""

    default_message = (
        "Live web research is temporarily paused due to Anakin API rate limits."
    )


class AnakinTimeoutError(AnakinServiceError):
    """Raised when an Anakin operation or agentic research job times out."""

    default_message = "Live web research operation timed out."


class AnakinNetworkError(AnakinServiceError, NetworkError):
    """Raised when network connectivity to Anakin fails."""

    default_message = "Network connection to Anakin API failed."


# =============================================================================
# NORMALIZED MODELS
# =============================================================================


@dataclass
class WebSource:
    """Normalized web source citation from search or research."""

    title: str
    url: str
    snippet: str = ""
    date: str | None = None
    index: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "date": self.date,
        }


@dataclass
class AnakinSearchResult:
    """Normalized structured outcome of an Anakin Web Search."""

    query: str
    sources: list[WebSource] = field(default_factory=list)
    summary: str = ""
    mode: str = "search"
    raw_id: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error_message: str | None = None

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "success": self.success,
            "source_count": self.source_count,
            "sources": [s.to_dict() for s in self.sources],
            "summary": self.summary,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
        }


@dataclass
class AnakinResearchResult:
    """Normalized structured outcome of an Anakin Agentic Deep Research job."""

    query: str
    summary: str
    structured_data: list[dict[str, Any]] | dict[str, Any] | None = None
    sources: list[WebSource] = field(default_factory=list)
    mode: str = "agentic_search"
    job_id: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error_message: str | None = None

    @property
    def source_count(self) -> int:
        return len(self.sources)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "mode": self.mode,
            "success": self.success,
            "summary": self.summary,
            "structured_data": self.structured_data,
            "source_count": self.source_count,
            "sources": [s.to_dict() for s in self.sources],
            "job_id": self.job_id,
            "duration_ms": round(self.duration_ms, 2),
            "error_message": self.error_message,
        }


# =============================================================================
# SERVICE IMPLEMENTATION
# =============================================================================


class AnakinService:
    """Official Anakin API integration providing real live web intelligence to NOVA."""

    def __init__(self, api_key: str | None = None) -> None:
        # Load API key securely without exposing it in logs or repr
        if api_key:
            self._api_key = api_key
        elif settings.anakin_api_key:
            self._api_key = settings.anakin_api_key.get_secret_value()
        else:
            self._api_key = os.getenv("ANAKIN_API_KEY", "")

        self._client: Any | None = None
        self._last_health: CapabilityHealth | None = None

    def __repr__(self) -> str:
        configured = bool(self._api_key and self._api_key.strip())
        return f"<AnakinService configured={configured}>"

    @property
    def is_configured(self) -> bool:
        """Check if an API key is available in configuration."""
        return bool(self._api_key and self._api_key.strip())

    def _get_client(self) -> Any:
        """Lazily initialize and return the official Anakin client."""
        if not self.is_configured:
            raise AnakinConfigurationError(
                "ANAKIN_API_KEY is not configured. Add ANAKIN_API_KEY to your .env file."
            )

        if self._client is None:
            try:
                from anakin import Anakin
                self._client = Anakin(api_key=self._api_key)
            except ImportError as exc:
                raise AnakinServiceError(
                    "anakin-sdk package is not installed. Install with 'pip install anakin-sdk'."
                ) from exc
            except Exception as exc:
                clean_err = self._sanitize_error(str(exc))
                raise AnakinServiceError(f"Failed to initialize Anakin client: {clean_err}") from exc

        return self._client

    def _sanitize_error(self, message: str) -> str:
        """Remove any inadvertent API key exposure from error text."""
        if not self._api_key:
            return message
        return message.replace(self._api_key, "[REDACTED]")

    # =========================================================================
    # HEALTH CHECK & CAPABILITY INTROSPECTION
    # =========================================================================

    def health_check(self, ping: bool = False) -> CapabilityHealth:
        """Return truthful runtime capability health."""
        # 1. Dependency Check
        try:
            import anakin
        except ImportError:
            health = CapabilityHealth(
                status=CapabilityStatus.DEPENDENCY_MISSING,
                is_available=False,
                details="anakin-sdk package is not installed in the current environment.",
            )
            self._last_health = health
            return health

        # 2. Configuration Check
        if not self.is_configured:
            health = CapabilityHealth(
                status=CapabilityStatus.CONFIGURATION_MISSING,
                is_available=False,
                details="ANAKIN_API_KEY is missing from .env or environment configuration.",
            )
            self._last_health = health
            return health

        # 3. Optional Ping (live verify key validity)
        if ping:
            try:
                client = self._get_client()
                # Run a minimal 1-result query to test auth
                client.search("ping", limit=1)
                health = CapabilityHealth(
                    status=CapabilityStatus.AVAILABLE,
                    is_available=True,
                    details="Anakin live web intelligence service is verified and operational.",
                )
            except Exception as exc:
                status = self._map_exception_to_status(exc)
                health = CapabilityHealth(
                    status=status,
                    is_available=False,
                    details=self._sanitize_error(str(exc)),
                )
            self._last_health = health
            return health

        # Default fast check based on configuration
        health = CapabilityHealth(
            status=CapabilityStatus.AVAILABLE,
            is_available=True,
            details="Anakin API key is configured and ready for live web intelligence.",
        )
        self._last_health = health
        return health

    def _map_exception_to_status(self, exc: Exception) -> CapabilityStatus:
        """Map SDK or HTTP exception to CapabilityStatus."""
        import anakin
        if isinstance(exc, anakin.AuthenticationError):
            return CapabilityStatus.AUTHENTICATION_FAILED
        if isinstance(exc, anakin.InsufficientCreditsError):
            return CapabilityStatus.INSUFFICIENT_CREDITS
        if isinstance(exc, anakin.RateLimitError):
            return CapabilityStatus.RATE_LIMITED
        return CapabilityStatus.TEMPORARILY_FAILED

    # =========================================================================
    # MODE 1: SYNCHRONOUS WEB SEARCH WITH CITATIONS
    # =========================================================================

    def search(self, query: str, limit: int = 5) -> AnakinSearchResult:
        """Perform a live web search using Anakin Search API.

        Args:
            query: The search query or prompt.
            limit: Maximum number of search results (default 5).

        Returns:
            AnakinSearchResult with normalized WebSource citations.
        """
        clean_query = query.strip()
        if not clean_query:
            return AnakinSearchResult(
                query=clean_query,
                success=False,
                error_message="Search query cannot be empty.",
            )

        client = self._get_client()
        start_time = time.monotonic()

        try:
            logger.info("Executing Anakin Live Web Search for: '%s' (limit=%d)", clean_query, limit)
            result = client.search(prompt=clean_query, limit=limit)
            duration = (time.monotonic() - start_time) * 1000

            sources: list[WebSource] = []
            for idx, item in enumerate(getattr(result, "results", []) or [], start=1):
                sources.append(
                    WebSource(
                        index=idx,
                        title=getattr(item, "title", "Untitled Source"),
                        url=getattr(item, "url", ""),
                        snippet=getattr(item, "snippet", "") or "",
                        date=getattr(item, "date", None),
                    )
                )

            logger.info(
                "Anakin Search returned %d sources in %.1fms for query '%s'",
                len(sources),
                duration,
                clean_query,
            )

            return AnakinSearchResult(
                query=clean_query,
                sources=sources,
                mode="search",
                raw_id=getattr(result, "id", "") or "",
                duration_ms=duration,
                success=True,
            )

        except Exception as exc:
            duration = (time.monotonic() - start_time) * 1000
            self._handle_exception(exc, context=f"search for '{clean_query}'")

    # =========================================================================
    # MODE 2: ASYNCHRONOUS DEEP AGENTIC MULTI-SOURCE RESEARCH
    # =========================================================================

    def agentic_research(
        self,
        query: str,
        timeout: float = 120.0,
        schema: dict[str, Any] | None = None,
    ) -> AnakinResearchResult:
        """Perform a multi-source deep research task using Anakin Agentic Search.

        Args:
            query: The research question or topic.
            timeout: Maximum seconds to wait for background research completion (default 120s).
            schema: Optional JSON schema for structured extraction.

        Returns:
            AnakinResearchResult with comprehensive summary, structured data, and sources.
        """
        clean_query = query.strip()
        if not clean_query:
            return AnakinResearchResult(
                query=clean_query,
                summary="",
                success=False,
                error_message="Research query cannot be empty.",
            )

        client = self._get_client()
        start_time = time.monotonic()

        try:
            logger.info(
                "Executing Anakin Agentic Deep Research for: '%s' (timeout=%.1fs)",
                clean_query,
                timeout,
            )

            # client.agentic_search automatically handles job submission, polling, and completion
            result = client.agentic_search(
                prompt=clean_query,
                use_browser=True,
                schema=schema,
                poll_timeout=timeout,
            )
            duration = (time.monotonic() - start_time) * 1000

            # Extract generatedJson
            generated = getattr(result, "generated_json", None)
            summary_text = getattr(generated, "summary", "") or ""
            structured_data = getattr(generated, "structured_data", None)

            # Extract any embedded URLs or citations from summary and structured data
            sources = self._extract_sources_from_research(summary_text, structured_data)

            logger.info(
                "Anakin Agentic Research completed job %s in %.1fs with %d chars summary",
                getattr(result, "id", "unknown"),
                duration / 1000.0,
                len(summary_text),
            )

            return AnakinResearchResult(
                query=clean_query,
                summary=summary_text,
                structured_data=structured_data,
                sources=sources,
                mode="agentic_search",
                job_id=getattr(result, "id", "") or "",
                duration_ms=duration,
                success=True,
            )

        except Exception as exc:
            self._handle_exception(exc, context=f"agentic research for '{clean_query}'")

    # =========================================================================
    # HELPERS & EXCEPTION TRANSLATION
    # =========================================================================

    def _extract_sources_from_research(
        self, summary: str, structured_data: Any
    ) -> list[WebSource]:
        """Extract referenced URLs from deep research summary text and structured data."""
        sources: list[WebSource] = []
        seen_urls: set[str] = set()

        # Regex for markdown links [Title](URL) or raw URLs
        md_links = re.findall(r"\[([^\]]+)\]\((https?://[^\s\)]+)\)", summary)
        for title, url in md_links:
            clean_url = url.rstrip(".,;)")
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                sources.append(
                    WebSource(
                        index=len(sources) + 1,
                        title=title.strip(),
                        url=clean_url,
                        snippet="",
                    )
                )

        raw_urls = re.findall(r"(https?://[^\s\)\],\"']+)", summary)
        for url in raw_urls:
            clean_url = url.rstrip(".,;)")
            if clean_url not in seen_urls:
                seen_urls.add(clean_url)
                domain = clean_url.split("/")[2] if "/" in clean_url else clean_url
                sources.append(
                    WebSource(
                        index=len(sources) + 1,
                        title=domain,
                        url=clean_url,
                        snippet="",
                    )
                )

        # Also inspect structured_data if it contains url fields
        if isinstance(structured_data, list):
            for item in structured_data:
                if isinstance(item, dict) and "url" in item:
                    u = str(item["url"]).strip()
                    if u.startswith("http") and u not in seen_urls:
                        seen_urls.add(u)
                        sources.append(
                            WebSource(
                                index=len(sources) + 1,
                                title=str(item.get("title") or item.get("name") or u),
                                url=u,
                                snippet=str(item.get("description") or ""),
                            )
                        )

        return sources

    def _handle_exception(self, exc: Exception, context: str) -> None:
        """Translate third-party exceptions into typed, sanitized NOVA errors."""
        import anakin

        clean_msg = self._sanitize_error(str(exc))
        logger.error("Anakin operation failed during %s: %s", context, clean_msg)

        if isinstance(exc, anakin.AuthenticationError):
            raise AnakinAuthenticationError(
                "Live web research failed: Anakin API key is invalid or expired. Check ANAKIN_API_KEY in .env."
            ) from exc

        if isinstance(exc, anakin.InsufficientCreditsError):
            raise AnakinInsufficientCreditsError(
                "Live web research unavailable: The Anakin account has insufficient credits."
            ) from exc

        if isinstance(exc, anakin.RateLimitError):
            raise AnakinRateLimitError(
                "Live web research temporarily unavailable: Anakin rate limit reached."
            ) from exc

        if isinstance(exc, anakin.JobTimeoutError):
            raise AnakinTimeoutError(
                "Deep web research timed out before Anakin completed the research job."
            ) from exc

        if isinstance(exc, (anakin.NetworkError, anakin.ServerError)):
            raise AnakinNetworkError(
                f"Network error connecting to Anakin live web intelligence: {clean_msg}"
            ) from exc

        if isinstance(exc, AnakinServiceError):
            raise exc

        raise AnakinServiceError(f"Live web research error: {clean_msg}") from exc


# Global default instance
anakin_service = AnakinService()
