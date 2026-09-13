"""Media player controls (Spotify, Music) and automated YouTube autoplay search extraction."""

from __future__ import annotations

import re
import subprocess
import urllib.parse
import urllib.request

from mac_control.models import CommandCategory, ExecutionResult, ExecutionStatus, MacCommand


def execute_media_command(cmd: MacCommand) -> ExecutionResult:
    """Execute playback actions or parse queries to launch YouTube autoplay streams."""
    action = cmd.action
    args = cmd.args

    try:
        if action == "play_song":
            song_query = args.get("song", "").strip()
            if not song_query:
                # If no song is specified, just resume playback
                return _toggle_play_state("play")

            # Attempt to retrieve first YouTube video ID for autoplay
            video_id = _get_first_youtube_video(song_query)
            if video_id:
                url = f"https://www.youtube.com/watch?v={video_id}"
                subprocess.run(["open", url], check=True)
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Playing '{song_query}' on YouTube",
                    command_name="Play Song (Autoplay)",
                    category=CommandCategory.MEDIA,
                    details={"song": song_query, "url": url}
                )
            else:
                # Fall back to opening search results
                url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(song_query)}"
                subprocess.run(["open", url], check=True)
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    message=f"Searching YouTube for '{song_query}'",
                    command_name="Play Song (Fallback)",
                    category=CommandCategory.MEDIA,
                    details={"song": song_query, "url": url}
                )

        elif action in ("pause", "resume", "stop", "next", "previous"):
            return _toggle_play_state(action)

    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Media control failed: {exc}",
            command_name="Media Control",
            category=CommandCategory.MEDIA
        )

    return ExecutionResult(
        status=ExecutionStatus.NOT_SUPPORTED,
        message=f"Unknown media action: {action}",
        command_name="Media Control",
        category=CommandCategory.MEDIA
    )

def _get_first_youtube_video(query: str) -> str | None:
    """Fetch search results from YouTube and extract the first video ID using regex."""
    try:
        query_encoded = urllib.parse.quote(query)
        url = f"https://www.youtube.com/results?search_query={query_encoded}"
        res = subprocess.run(
            [
                "curl", "-s", "-L", "--max-time", "3",
                "-A", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                url
            ],
            capture_output=True,
            text=True,
            check=False
        )
        if res.returncode == 0 and res.stdout:
            # Match standard watch?v= video ID formats
            video_ids = re.findall(r"watch\?v=(\S{11})", res.stdout)
            if video_ids:
                return video_ids[0]
    except Exception:
        pass
    return None

def _toggle_play_state(state: str) -> ExecutionResult:
    """Send play state change commands to active music player (Spotify or Apple Music)."""
    player = _get_active_player()

    if not player:
        # Default fallback to Apple Music
        player = "Music"

    # Map command states to AppleScript verbs
    script_verbs = {
        "play": "play",
        "resume": "play",
        "pause": "pause",
        "stop": "stop",
        "next": "next track",
        "previous": "previous track"
    }

    verb = script_verbs.get(state, "play")

    try:
        script = f'tell application "{player}" to {verb}'
        subprocess.run(["osascript", "-e", script], check=True)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            message=f"Sent {state} command to {player}",
            command_name=f"Media {state.title()}",
            category=CommandCategory.MEDIA
        )
    except Exception as exc:
        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            message=f"Failed to control {player}: {exc}",
            command_name="Media Playback",
            category=CommandCategory.MEDIA
        )

def _get_active_player() -> str | None:
    """Determine which media player application is currently running."""
    try:
        # Check Spotify
        res = subprocess.run(
            ["osascript", "-e", 'application "Spotify" is running'],
            capture_output=True, text=True, check=True
        )
        if res.stdout.strip() == "true":
            return "Spotify"

        # Check Apple Music
        res = subprocess.run(
            ["osascript", "-e", 'application "Music" is running'],
            capture_output=True, text=True, check=True
        )
        if res.stdout.strip() == "true":
            return "Music"
    except Exception:
        pass
    return None
