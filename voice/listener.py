"""Continuous background audio listening and speech segment coordinator for NOVA Voice V2."""

from __future__ import annotations

import threading
import time
from typing import Callable

import numpy as np

from core.logger import get_logger
from voice.microphone import MicrophoneManager
from voice.state import VADState, VoiceState
from voice.vad import VoiceActivityDetector

logger = get_logger(__name__)


class VoiceListener:
    """Runs a dedicated background loop reading microphone chunks and running VAD."""

    def __init__(
        self,
        microphone: MicrophoneManager,
        vad: VoiceActivityDetector,
        on_speech_finalized: Callable[[np.ndarray], None],
        get_voice_state: Callable[[], VoiceState],
    ) -> None:
        self.microphone = microphone
        self.vad = vad
        self.on_speech_finalized = on_speech_finalized
        self.get_voice_state = get_voice_state

        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the background listening worker thread."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self.microphone.start_capture()
            self.vad.reset()

            self._thread = threading.Thread(
                target=self._listening_loop,
                name="nova-voice-listener",
                daemon=True,
            )
            self._thread.start()
            logger.info("VoiceListener thread started.")

    def stop(self) -> None:
        """Stop the background listening worker."""
        with self._lock:
            self._running = False

        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=1.0)
            self._thread = None

        self.microphone.stop_capture()
        self.vad.reset()
        logger.info("VoiceListener thread stopped.")

    def is_active(self) -> bool:
        """Return True if the listener thread is currently running."""
        with self._lock:
            return self._running and self._thread is not None and self._thread.is_alive()

    def _listening_loop(self) -> None:
        """Continuous audio pump loop."""
        while self._running:
            try:
                # Check current application voice state
                current_state = self.get_voice_state()

                # If NOVA is actively speaking or muted, drain mic queue to ignore echo
                if current_state in (VoiceState.SPEAKING, VoiceState.MUTED, VoiceState.PROCESSING):
                    self.microphone.clear_queue()
                    self.vad.reset()
                    time.sleep(0.05)
                    continue

                # Read one float32 frame from microphone
                chunk = self.microphone.read_chunk(timeout=0.08)
                if chunk is None:
                    continue

                # Process chunk through Voice Activity Detector
                vad_state, finalized_audio = self.vad.process_chunk(chunk)

                if vad_state == VADState.SPEECH_FINALIZED and finalized_audio is not None:
                    if len(finalized_audio) > 0:
                        logger.debug("VoiceListener: Speech finalized with %d samples.", len(finalized_audio))
                        try:
                            self.on_speech_finalized(finalized_audio)
                        except Exception as exc:
                            logger.error("Error in on_speech_finalized callback: %s", exc, exc_info=True)

            except Exception as exc:
                if self._running:
                    logger.error("Unexpected error in VoiceListener loop: %s", exc, exc_info=True)
                    time.sleep(0.1)
