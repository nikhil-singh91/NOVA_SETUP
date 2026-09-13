"""Web browser control links and search engine queries."""

from __future__ import annotations

import subprocess
import urllib.parse

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand

WEBSITE_MAP = {
    "github": "https://github.com",
    "leetcode": "https://leetcode.com",
    "codechef": "https://codechef.com",
    "chatgpt": "https://chatgpt.com",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "drive": "https://drive.google.com",
    "notion": "https://notion.so",
    "youtube": "https://youtube.com",
    "google": "https://google.com"
}

def execute_browser_command(cmd: MacCommand) -> ExecutionResult:
    """Execute web browser navigation and query search commands."""
    action = cmd.action
    args = cmd.args

    try:
        if action == "open_website":
            site = args.get("site", "").lower().strip()
            url = WEBSITE_MAP.get(site)

            if not url:
                # If it's a domain/URL directly
                if "." in site:
                    url = site if site.startswith(("http://", "https://")) else f"https://{site}"
                else:
                    url = f"https://www.google.com/search?q={urllib.parse.quote(site)}"

            subprocess.run(["open", url], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Opened website: {url}",
                command_name="Open Website",
                category=CommandCategory.BROWSER,
                details={"url": url}
            )

        elif action == "google_search":
            query = args.get("query", "").strip()
            if not query:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message="No search query specified",
                    command_name="Google Search",
                    category=CommandCategory.BROWSER
                )
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            subprocess.run(["open", url], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Searched Google for: {query}",
                command_name="Google Search",
                category=CommandCategory.BROWSER,
                details={"query": query, "url": url}
            )

        elif action == "youtube_search":
            query = args.get("query", "").strip()
            if not query:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    message="No search query specified",
                    command_name="YouTube Search",
                    category=CommandCategory.BROWSER
                )
            url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(query)}"
            subprocess.run(["open", url], check=True)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                message=f"Searched YouTube for: {query}",
                command_name="YouTube Search",
                category=CommandCategory.BROWSER,
                details={"query": query, "url": url}
            )

    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Browser command failed: {exc}",
            command_name="Browser Control",
            category=CommandCategory.BROWSER
        )

    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown browser action: {action}",
        command_name="Browser Control",
        category=CommandCategory.BROWSER
    )
