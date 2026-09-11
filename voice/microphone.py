"""Microphone discovery, device selection, and low-latency audio capture for NOVA Voice V2."""

from __future__ import annotations

import queue
import sys
import threading
import time
from typing import Any, Callable

import numpy as np
import pyaudio

from core.logger import get_logger

logger = get_logger(__name__)

# Default Audio Specifications
DEFAULT_SAMPLE_RATE = 16000
DEFAULT_CHANNELS = 1
DEFAULT_CHUNK_SIZE = 512  # ~32ms at 16kHz
DEFAULT_FORMAT = pyaudio.paInt16


class MicrophoneError(Exception):
    """Raised when audio hardware capture or initialization fails."""


class MicrophoneManager:
    """Manages PyAudio hardware streams and provides a non-blocking queue of audio chunks.

    Attributes:
        sample_rate: Audio sampling frequency in Hz (default: 16000).
        chunk_size: Number of samples per frame (default: 512 = 32ms).
        device_index: Specific device index to use, or None for system default.
    """

    def __init__(
        self,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        device_index: int | None = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.device_index = device_index

        self._pyaudio: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._is_capturing = False
        self._lock = threading.RLock()
        self._audio_queue: queue.Queue[bytes] = queue.Queue(maxsize=200)

        self._last_rms = 0.0
        self._last_peak = 0.0
        self._total_chunks_read = 0

    @staticmethod
    def list_input_devices() -> list[dict[str, Any]]:
        """List all available audio input devices on the system."""
        p = pyaudio.PyAudio()
        devices: list[dict[str, Any]] = []
        try:
            device_count = p.get_device_count()
            for idx in range(device_count):
                try:
                    info = p.get_device_info_by_host_api_device_index(0, idx)
                    if info.get("maxInputChannels", 0) > 0:
                        devices.append({
                            "index": idx,
                            "name": info.get("name", f"Device {idx}"),
                            "channels": info.get("maxInputChannels", 1),
                            "sample_rate": int(info.get("defaultSampleRate", 16000)),
                        })
                except Exception:
                    continue
        finally:
            p.terminate()
        return devices

    def initialize(self) -> None:
        """Initialize the PyAudio subsystem."""
        with self._lock:
            if self._pyaudio is None:
                try:
                    self._pyaudio = pyaudio.PyAudio()
                    logger.info("MicrophoneManager PyAudio initialized successfully.")
                except Exception as exc:
                    logger.error("Failed to initialize PyAudio: %s", exc)
                    raise MicrophoneError(f"Could not initialize PyAudio subsystem: {exc}") from exc

    def start_capture(self) -> None:
        """Open the microphone stream and start feeding the internal audio queue."""
        with self._lock:
            if self._is_capturing:
                return

            if self._pyaudio is None:
                self.initialize()

            assert self._pyaudio is not None

            self.clear_queue()
            self._is_capturing = True

            def _audio_callback(
                in_data: bytes | None,
                frame_count: int,
                time_info: dict[str, float],
                status_flags: int,
            ) -> tuple[bytes | None, int]:
                if in_data and self._is_capturing:
                    try:
                        self._audio_queue.put_nowait(in_data)
                    except queue.Full:
                        try:
                            # Drop oldest chunk to keep stream real-time
                            self._audio_queue.get_nowait()
                            self._audio_queue.put_nowait(in_data)
                        except (queue.Empty, queue.Full):
                            pass
                return (None, pyaudio.paContinue)

            try:
                stream_kwargs: dict[str, Any] = {
                    "format": DEFAULT_FORMAT,
                    "channels": DEFAULT_CHANNELS,
                    "rate": self.sample_rate,
                    "input": True,
                    "frames_per_buffer": self.chunk_size,
                    "stream_callback": _audio_callback,
                }
                if self.device_index is not None:
                    stream_kwargs["input_device_index"] = self.device_index

                self._stream = self._pyaudio.open(**stream_kwargs)
                self._stream.start_stream()
                logger.info(
                    "Microphone stream started (rate=%d, chunk_size=%d, device=%s).",
                    self.sample_rate,
                    self.chunk_size,
                    self.device_index if self.device_index is not None else "default",
                )
            except Exception as exc:
                self._is_capturing = False
                logger.error("Failed to open audio input stream: %s", exc)
                raise MicrophoneError(f"Failed to open microphone input stream: {exc}") from exc

    def stop_capture(self) -> None:
        """Stop and close the audio stream."""
        with self._lock:
            self._is_capturing = False
            if self._stream is not None:
                try:
                    if self._stream.is_active():
                        self._stream.stop_stream()
                    self._stream.close()
                except Exception as exc:
                    logger.debug("Exception while closing mic stream: %s", exc)
                finally:
                    self._stream = None

            self.clear_queue()
            logger.info("Microphone stream stopped.")

    def read_chunk(self, timeout: float = 0.1) -> np.ndarray | None:
        """Read one frame of audio as a float32 normalized NumPy array in range [-1.0, 1.0].

        Args:
            timeout: Maximum seconds to wait for a frame.

        Returns:
            Normalized float32 numpy array, or None if timeout elapsed.
        """
        try:
            raw_bytes = self._audio_queue.get(timeout=timeout)
        except queue.Empty:
            return None

        # Convert int16 bytes to normalized float32
        int16_data = np.frombuffer(raw_bytes, dtype=np.int16)
        float32_data = int16_data.astype(np.float32) / 32768.0

        # Update telemetry
        self._total_chunks_read += 1
        if len(float32_data) > 0:
            self._last_rms = float(np.sqrt(np.mean(float32_data ** 2)))
            self._last_peak = float(np.max(np.abs(float32_data)))

        return float32_data

    def clear_queue(self) -> None:
        """Discard all pending audio frames from the buffer."""
        while not self._audio_queue.empty():
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                break

    def get_metrics(self) -> dict[str, Any]:
        """Return real-time audio metrics for UI/diagnostics."""
        with self._lock:
            return {
                "is_capturing": self._is_capturing,
                "last_rms": self._last_rms,
                "last_peak": self._last_peak,
                "queue_size": self._audio_queue.qsize(),
                "sample_rate": self.sample_rate,
                "device_index": self.device_index,
            }

    def shutdown(self) -> None:
        """Cleanly terminate audio streams and PyAudio instance."""
        with self._lock:
            self.stop_capture()
            if self._pyaudio is not None:
                try:
                    self._pyaudio.terminate()
                except Exception as exc:
                    logger.debug("Exception during PyAudio termination: %s", exc)
                finally:
                    self._pyaudio = None
            logger.info("MicrophoneManager shut down.")
