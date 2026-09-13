"""Real Live Smoke Test for Anakin API Live Web Intelligence.

Executes genuine requests against the live Anakin API using the ANAKIN_API_KEY
configured in the environment. Tests synchronous web search and capability health.
NEVER fakes results or prints the raw API key.
"""

from __future__ import annotations

import sys
import time

from config.settings import settings
from services.anakin_service import (
    AnakinAuthenticationError,
    AnakinInsufficientCreditsError,
    AnakinRateLimitError,
    AnakinService,
    CapabilityStatus,
    anakin_service,
)


def run_live_smoke_test() -> bool:
    print("==================================================")
    print("NOVA LIVE ANAKIN API SMOKE TEST")
    print("==================================================")

    # 1. Configuration check
    print("\n[Step 1] Checking configuration...")
    if not anakin_service.is_configured:
        print("FAIL: ANAKIN_API_KEY is not configured in .env or environment.")
        return False
    print("PASS: ANAKIN_API_KEY is present and configured (key redacted).")

    # 2. Capability Health check
    print("\n[Step 2] Introspecting capability health...")
    health = anakin_service.health_check(ping=False)
    print(f"Capability Status: {health.status.value}")
    print(f"Capability Available: {health.is_available}")
    if not health.is_available:
        print(f"FAIL: Capability health is unavailable: {health.details}")
        return False
    print("PASS: Capability health is AVAILABLE.")

    # 3. Real live search request
    print("\n[Step 3] Executing REAL Anakin Live Web Search...")
    query = "Anakin Forge hackathon 2026"
    start_time = time.monotonic()
    try:
        result = anakin_service.search(query=query, limit=3)
        duration_ms = (time.monotonic() - start_time) * 1000

        if not result.success:
            print(f"FAIL: Anakin search returned failure: {result.error_message}")
            return False

        print(f"PASS: Live Anakin Search succeeded in {duration_ms:.1f}ms!")
        print(f"Found {result.source_count} verified sources:")
        for source in result.sources:
            print(f"  [{source.index}] {source.title}")
            print(f"      URL: {source.url}")
            if source.snippet:
                print(f"      Snippet: {source.snippet[:100]}...")

        if result.source_count == 0:
            print("WARNING: Live search returned 0 results.")
            return False

    except AnakinAuthenticationError as exc:
        print(f"FAIL: Authentication error - API key is invalid or expired: {exc}")
        return False
    except AnakinInsufficientCreditsError as exc:
        print(f"FAIL: Insufficient credits on Anakin account: {exc}")
        return False
    except AnakinRateLimitError as exc:
        print(f"FAIL: Anakin rate limit reached: {exc}")
        return False
    except Exception as exc:
        print(f"FAIL: Unexpected error during live search: {exc}")
        return False

    print("\n==================================================")
    print("SMOKE TEST RESULT: ALL LIVE CHECKS PASSED")
    print("==================================================")
    return True


if __name__ == "__main__":
    success = run_live_smoke_test()
    sys.exit(0 if success else 1)
