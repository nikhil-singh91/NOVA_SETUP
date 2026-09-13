"""Unit tests for AnakinService (Live Web Intelligence)."""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

from services.anakin_service import (
    AnakinAuthenticationError,
    AnakinConfigurationError,
    AnakinInsufficientCreditsError,
    AnakinNetworkError,
    AnakinRateLimitError,
    AnakinResearchResult,
    AnakinSearchResult,
    AnakinService,
    AnakinTimeoutError,
    CapabilityHealth,
    CapabilityStatus,
    WebSource,
)


class TestAnakinServiceUnit:
    """Comprehensive unit testing of AnakinService with mocked SDK responses."""

    def test_missing_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """1. When ANAKIN_API_KEY is missing, service reports configuration missing."""
        monkeypatch.delenv("ANAKIN_API_KEY", raising=False)
        with patch("config.settings.settings.anakin_api_key", None):
            service = AnakinService(api_key="")
            assert not service.is_configured
            health = service.health_check()
            assert health.status == CapabilityStatus.CONFIGURATION_MISSING
            assert not health.is_available
            with pytest.raises(AnakinConfigurationError):
                service.search("test query")

    def test_invalid_api_key_authentication_error(self) -> None:
        """2. When API key is rejected (401), raises typed AnakinAuthenticationError."""
        import anakin

        mock_client = MagicMock()
        mock_client.search.side_effect = anakin.AuthenticationError(
            "Invalid API key provided", status_code=401, code="invalid_api_key", body={}
        )

        service = AnakinService(api_key="ask_invalid_key_123")
        service._client = mock_client

        with pytest.raises(AnakinAuthenticationError) as exc_info:
            service.search("test query")
        assert "invalid or expired" in str(exc_info.value).lower()

    def test_successful_search_with_citations(self) -> None:
        """3. Successful search returns normalized WebSource items."""
        mock_item1 = MagicMock(
            title="NVIDIA Blackwell Architecture",
            url="https://nvidia.com/blackwell",
            snippet="Overview of NVIDIA Blackwell GPU architecture.",
            date="2026-03-15",
        )
        mock_item2 = MagicMock(
            title="AI Hardware 2026",
            url="https://techradar.com/ai-chips",
            snippet="Latest developments in AI accelerator chips.",
            date="2026-03-10",
        )
        mock_response = MagicMock(id="search-req-999", results=[mock_item1, mock_item2])

        mock_client = MagicMock()
        mock_client.search.return_value = mock_response

        service = AnakinService(api_key="ask_test_key")
        service._client = mock_client

        res = service.search("NVIDIA Blackwell", limit=2)
        assert isinstance(res, AnakinSearchResult)
        assert res.success
        assert res.source_count == 2
        assert res.sources[0].title == "NVIDIA Blackwell Architecture"
        assert res.sources[0].url == "https://nvidia.com/blackwell"
        assert res.sources[0].index == 1
        assert res.sources[1].index == 2

    def test_search_network_failure(self) -> None:
        """4. Network failure raises AnakinNetworkError."""
        import anakin

        mock_client = MagicMock()
        mock_client.search.side_effect = anakin.NetworkError("Connection refused by peer")

        service = AnakinService(api_key="ask_test_key")
        service._client = mock_client

        with pytest.raises(AnakinNetworkError):
            service.search("network test")

    def test_search_timeout(self) -> None:
        """5. Timeout during search raises typed AnakinTimeoutError or AnakinNetworkError."""
        import anakin

        mock_client = MagicMock()
        mock_client.search.side_effect = anakin.JobTimeoutError("Search request timed out")

        service = AnakinService(api_key="ask_test_key")
        service._client = mock_client

        with pytest.raises(AnakinTimeoutError):
            service.search("timeout query")

    def test_search_rate_limit(self) -> None:
        """6. Rate limit (429) raises typed AnakinRateLimitError."""
        import anakin

        mock_client = MagicMock()
        mock_client.search.side_effect = anakin.RateLimitError(
            "Rate limit exceeded. Try again in 30 seconds.", status_code=429, code="rate_limit", body={}
        )

        service = AnakinService(api_key="ask_test_key")
        service._client = mock_client

        with pytest.raises(AnakinRateLimitError):
            service.search("rate limited query")

    def test_insufficient_credits(self) -> None:
        """7. Insufficient credits (402) raises typed AnakinInsufficientCreditsError."""
        import anakin

        mock_client = MagicMock()
        mock_client.search.side_effect = anakin.InsufficientCreditsError(
            "Account has 0 credits remaining", status_code=402, code="insufficient_credits", body={}
        )

        service = AnakinService(api_key="ask_test_key")
        service._client = mock_client

        with pytest.raises(AnakinInsufficientCreditsError):
            service.search("credits query")

    def test_successful_agentic_research(self) -> None:
        """8. Successful Agentic Research returns summary and parsed structured data."""
        mock_generated = MagicMock()
        mock_generated.summary = (
            "Here is the comparison of top AI agents. "
            "See [NOVA Framework](https://github.com/nova) and [LangChain](https://langchain.com)."
        )
        mock_generated.structured_data = [
            {"name": "NOVA", "url": "https://github.com/nova", "score": 95},
            {"name": "AutoGPT", "url": "https://autogpt.com", "score": 88},
        ]
        mock_response = MagicMock(
            id="agentic-job-777",
            status="completed",
            generated_json=mock_generated,
        )

        mock_client = MagicMock()
        mock_client.agentic_search.return_value = mock_response

        service = AnakinService(api_key="ask_test_key")
        service._client = mock_client

        res = service.agentic_research("Compare top AI agents in 2026")
        assert isinstance(res, AnakinResearchResult)
        assert res.success
        assert res.job_id == "agentic-job-777"
        assert "NOVA Framework" in res.summary
        assert res.source_count >= 2
        # Verify URLs were preserved
        urls = [s.url for s in res.sources]
        assert "https://github.com/nova" in urls

    def test_agentic_research_failure(self) -> None:
        """9. Agentic research failure raises typed exception."""
        import anakin

        mock_client = MagicMock()
        mock_client.agentic_search.side_effect = anakin.JobTimeoutError(
            "Agentic search job 123 timed out after 120s"
        )

        service = AnakinService(api_key="ask_test_key")
        service._client = mock_client

        with pytest.raises(AnakinTimeoutError):
            service.agentic_research("Unfinished job")

    def test_capability_health_reporting(self) -> None:
        """10. Capability health returns structured report without leaking secrets."""
        service = AnakinService(api_key="ask_super_secret_key_99999")
        health = service.health_check(ping=False)
        assert isinstance(health, CapabilityHealth)
        assert health.status == CapabilityStatus.AVAILABLE
        assert health.is_available
        assert health.required_dependency == "anakin-sdk"
        assert health.required_env_var == "ANAKIN_API_KEY"

        # Check to_dict format
        d = health.to_dict()
        assert d["status"] == "AVAILABLE"
        assert "super_secret" not in str(d)

    def test_secret_redaction(self) -> None:
        """18. Secrets never appear in service repr or error messages."""
        secret = "ask_my_secret_key_12345678"
        service = AnakinService(api_key=secret)

        # Repr check
        repr_str = repr(service)
        assert secret not in repr_str
        assert "configured=True" in repr_str

        # Sanitization check
        raw_msg = f"Error occurred with key {secret} on server"
        clean_msg = service._sanitize_error(raw_msg)
        assert secret not in clean_msg
        assert "[REDACTED]" in clean_msg
