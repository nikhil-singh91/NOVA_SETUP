"""Text-to-Speech (TTS) engine and audio playback manager for NOVA Voice V2."""

from __future__ import annotations

import asyncio
import os
import queue
import re
import subprocess
import tempfile
import threading
import time
from typing import Any, Callable

from config.settings import settings
from core.logger import get_logger
from voice.state import SpeechOutputResult

logger = get_logger(__name__)


from core.response_cleaner import clean_model_response


_EMOJI_AND_SYMBOL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?:"
    r"[\U00010000-\U0010ffff]"  # Supplementary Multilingual Planes (emojis, pictographs, symbols)
    r"|[\u2600-\u27bf]"          # Misc symbols & Dingbats (❤️, ☀️, ⚡, ❄️, ☕, ❌, etc.)
    r"|[\u2300-\u23ff]"          # Misc technical (⌚, ⌛, ⌨️, etc.)
    r"|[\u2b00-\u2bff]"          # Misc symbols and arrows (⭐, ⭕, etc.)
    r"|[\u25a0-\u25ff]"          # Geometric shapes
    r"|[\u2190-\u21ff]"          # Arrows
    r"|[\u20d0-\u20ff]"          # Combining diacritical marks for symbols
    r"|[\ufe00-\ufe0f]"          # Variation selectors (\ufe0f emoji presentation)
    r"|[\u200d]"                 # Zero-width joiner
    r")+"
)


def clean_text_for_speech(text: str) -> str:
    """Sanitize text before speech synthesis.

    Removes code blocks, markdown symbols, URLs, asterisks, emojis, and extraneous punctuation.
    Leaves normal speech punctuation intact while ensuring emojis are omitted or replaced with a natural pause.
    """
    if not text:
        return ""

    cleaned = clean_model_response(text, default_fallback="")

    # 1. Remove markdown code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " [code snippet omitted] ", cleaned)
    # 2. Remove inline code
    cleaned = re.sub(r"`[^`]*`", "", cleaned)
    # 3. Replace markdown links [text](url) -> text
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    # 4. Remove standalone URLs
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    # 5. Remove hash symbols / headers
    cleaned = re.sub(r"#+", "", cleaned)
    # 6. Remove markdown bold/italic asterisks and underscores
    cleaned = re.sub(r"[*_~]{1,3}", "", cleaned)

    # 7. Remove emojis & non-speech symbols:
    # If an emoji sits between two words without surrounding punctuation (e.g. "Yesss 😂 finally!"),
    # replace it with a gentle pause comma (", ") to maintain natural speech cadence.
    # Otherwise, omit it cleanly.
    def _emoji_sub(match: re.Match[str]) -> str:
        start = match.start()
        end = match.end()
        pre = cleaned[:start].rstrip()
        post = cleaned[end:].lstrip()
        if pre and pre[-1] not in ",.!?—:;(-" and post and post[0] not in ",.!?—:;)":
            return ", "
        return " "

    cleaned = _EMOJI_AND_SYMBOL_PATTERN.sub(_emoji_sub, cleaned)

    # 8. Clean up whitespace and redundant punctuation
    cleaned = re.sub(r"\s+([,!?.:;])", r"\1", cleaned)
    cleaned = re.sub(r",+", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned



class SpeakerManager:
    """Manages speech synthesis and audio playback with queuing and interruption support."""

    def __init__(
        self,
        voice: str = "hi-IN-SwaraNeural",
        rate: str = "+0%",
        volume: str = "+0%",
        primary_engine: str = "edge_tts",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.primary_engine = primary_engine

        self._is_speaking = False
        self._stop_requested = threading.Event()
        self._lock = threading.RLock()
        self._speech_queue: queue.Queue[tuple[str, Callable[[SpeechOutputResult], None] | None]] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._running = False

        # Initialize pygame mixer for low latency local audio playback
        self._pygame_initialized = False

    def initialize(self) -> None:
        """Initialize the audio playback subsystem and background worker thread."""
        with self._lock:
            if not self._pygame_initialized:
                try:
                    import pygame
                    pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=1024)
                    self._pygame_initialized = True
                    logger.info("SpeakerManager: Pygame audio mixer initialized.")
                except Exception as exc:
                    logger.warning("Could not initialize pygame mixer: %s. Will use system fallback.", exc)

            if not self._running:
                self._running = True
                self._stop_requested.clear()
                self._worker_thread = threading.Thread(
                    target=self._speech_worker_loop,
                    name="nova-speaker-worker",
                    daemon=True,
                )
                self._worker_thread.start()
                logger.info("SpeakerManager initialized and worker started.")

    @property
    def is_speaking(self) -> bool:
        """Return True if speech synthesis or audio playback is currently active."""
        with self._lock:
            return self._is_speaking

    def speak(self, text: str) -> SpeechOutputResult:
        """Synchronously speak the given text, blocking until playback finishes."""
        cleaned = clean_text_for_speech(text)
        if not cleaned:
            return SpeechOutputResult(success=True, text=text, duration_seconds=0.0)

        with self._lock:
            self._is_speaking = True
            self._stop_requested.clear()

        start_t = time.monotonic()
        try:
            # 1. Try Edge-TTS first if configured
            if self.primary_engine == "edge_tts":
                success = self._synthesize_and_play_edge_tts(cleaned)
                if success:
                    duration = time.monotonic() - start_t
                    return SpeechOutputResult(
                        success=True,
                        text=cleaned,
                        duration_seconds=duration,
                        engine_name="edge_tts",
                    )

            # 2. Fallback to pyttsx3 or macOS say
            success = self._speak_fallback(cleaned)
            duration = time.monotonic() - start_t
            return SpeechOutputResult(
                success=success,
                text=cleaned,
                duration_seconds=duration,
                engine_name="say_fallback",
            )
        except Exception as exc:
            logger.error("Speech synthesis failed: %s", exc, exc_info=True)
            return SpeechOutputResult(
                success=False,
                text=cleaned,
                duration_seconds=time.monotonic() - start_t,
                error=str(exc),
            )
        finally:
            with self._lock:
                self._is_speaking = False
            # Small settling pause to allow room echo to dissipate
            time.sleep(0.35)

    def speak_async(
        self,
        text: str,
        on_complete: Callable[[SpeechOutputResult], None] | None = None,
    ) -> None:
        """Enqueue speech to be synthesized and played asynchronously in the background."""
        if not self._running:
            self.initialize()
        self._speech_queue.put((text, on_complete))

    def stop(self) -> None:
        """Immediately stop and cancel any currently playing or queued speech."""
        with self._lock:
            self._stop_requested.set()
            # Drain queue
            while not self._speech_queue.empty():
                try:
                    self._speech_queue.get_nowait()
                except queue.Empty:
                    break

            if self._pygame_initialized:
                try:
                    import pygame
                    pygame.mixer.music.stop()
                except Exception:
                    pass

            self._is_speaking = False
            logger.info("Speech playback interrupted and queue cleared.")

    def _speech_worker_loop(self) -> None:
        """Worker thread processing queued speech jobs."""
        while self._running:
            try:
                item = self._speech_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            text, on_complete = item
            if self._stop_requested.is_set():
                self._stop_requested.clear()
                continue

            result = self.speak(text)

            if on_complete is not None:
                try:
                    on_complete(result)
                except Exception as exc:
                    logger.error("Error in speech on_complete callback: %s", exc)

    def _synthesize_and_play_edge_tts(self, text: str) -> bool:
        """Synthesize audio with edge-tts and play via pygame.mixer."""
        try:
            import edge_tts

            temp_path = None
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name

            # Run async edge-tts generation synchronously
            async def _generate():
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=self.voice,
                    rate=self.rate,
                    volume=self.volume,
                )
                await communicate.save(temp_path)

            asyncio.run(_generate())

            if self._stop_requested.is_set():
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                return False

            # Play audio file
            if self._pygame_initialized:
                import pygame
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()

                while pygame.mixer.music.get_busy() and not self._stop_requested.is_set():
                    time.sleep(0.05)

                if self._stop_requested.is_set():
                    pygame.mixer.music.stop()
            else:
                # Play using macOS afplay
                proc = subprocess.Popen(["afplay", temp_path])
                while proc.poll() is None and not self._stop_requested.is_set():
                    time.sleep(0.05)
                if self._stop_requested.is_set():
                    proc.terminate()

            if os.path.exists(temp_path):
                os.unlink(temp_path)

            return not self._stop_requested.is_set()

        except Exception as exc:
            logger.warning("Edge-TTS synthesis failed: %s. Attempting fallback.", exc)
            return False

    def _speak_fallback(self, text: str) -> bool:
        """Fallback speech using macOS native 'say' command or pyttsx3."""
        try:
            # macOS native say command is 100% reliable offline
            proc = subprocess.Popen(["say", text])
            while proc.poll() is None and not self._stop_requested.is_set():
                time.sleep(0.05)
            if self._stop_requested.is_set():
                proc.terminate()
            return True
        except Exception:
            try:
                import pyttsx3
                engine = pyttsx3.init()
                engine.say(text)
                engine.runAndWait()
                return True
            except Exception as exc:
                logger.error("Fallback speech also failed: %s", exc)
                return False

    def shutdown(self) -> None:
        """Stop worker and release audio resources."""
        with self._lock:
            self._running = False
            self.stop()

            if self._pygame_initialized:
                try:
                    import pygame
                    pygame.mixer.quit()
                except Exception:
                    pass
                self._pygame_initialized = False

            logger.info("SpeakerManager shut down.")
