"""Transcription layer for NOVA Voice V2 with pluggable local and cloud backends."""

from __future__ import annotations

import io
import time
from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from config.settings import settings
from core.logger import get_logger
from voice.state import TranscriptionResult

logger = get_logger(__name__)


class BaseTranscriber(ABC):
    """Abstract contract for speech-to-text engines."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Return the unique name of this transcriber."""

    @abstractmethod
    def initialize(self) -> None:
        """Initialize models, clients, or local resources."""

    @abstractmethod
    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe a float32 normalized audio buffer into text.

        Args:
            audio: 1D float32 numpy array containing speech.
            sample_rate: Audio sampling frequency in Hz.
            language: Optional language code hint (e.g. "en", "hi").

        Returns:
            A structured TranscriptionResult.
        """

    @abstractmethod
    def shutdown(self) -> None:
        """Release any held memory or resources."""


# Domain vocabulary prompt and hotwords to eliminate phonetic mishearings and bias Whisper towards assistant commands and entities
ASSISTANT_DOMAIN_PROMPT: str = (
    "NOVA desktop voice assistant commands and conversational Hinglish: "
    "Nova, open Telegram, open YouTube, WhatsApp, GitHub, Flipkart, Amazon, Google, VS Code, Terminal. "
    "Nova write code in notepad, explain recursion, binary search, DSA, trees, graphs, python, cpp, bug fix. "
    "Nova aaj college mein bahut thak gaya hoon, main abhi college se aaya hoon, pura din class thi. "
    "Nova ye recursion samajh nahi aa rahi, yaar ye bug solve nahi ho raha, mujhe ye code samjha do. "
    "Nova I was studying DSA aur ye topic samajh nahi aa raha, kal mera exam hai and mujhe kuch yaad nahi hai. "
    "Nova volume thoda badha do, turn volume up, bluetooth off, screenshot lo, Telegram open kar do, Telegram kholo, app band karo, "
    "mujhe batao, kya ho raha hai, songs bhajao, gaana chalao, play song, play shorts, open youtube shorts, what are you seeing on my screen, screen pe kya hai, search Flipkart pe mobile phones, shut down."
)

ASSISTANT_HOTWORDS: str = (
    "telegram, youtube, whatsapp, github, flipkart, google, vscode, terminal, "
    "recursion, dsa, bubble sort, binary search, code, python, cpp, bug, "
    "thak gaya, college, exam, samjha do, samajh, nahi ho raha, run nahi ho raha, "
    "badha do, kar do, kholo, band karo, bhajao, bajao, chala do, gaana, songs, shorts, screen, volume, brightness, wifi, bluetooth, screenshot"
)


class FasterWhisperTranscriber(BaseTranscriber):
    """Local, offline speech transcriber powered by faster-whisper (CTranslate2)."""

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._initialized = False

    @property
    def name(self) -> str:
        return f"faster_whisper_{self.model_size}"

    def initialize(self) -> None:
        if self._initialized and self._model is not None:
            return

        from faster_whisper import WhisperModel

        logger.info(
            "Loading local FasterWhisper model '%s' (device=%s, compute_type=%s)...",
            self.model_size,
            self.device,
            self.compute_type,
        )
        start_t = time.monotonic()
        self._model = WhisperModel(
            self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            cpu_threads=4,
        )
        self._initialized = True
        elapsed = time.monotonic() - start_t
        logger.info("FasterWhisper model '%s' initialized in %.2fs.", self.model_size, elapsed)

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        if not self._initialized or self._model is None:
            self.initialize()

        assert self._model is not None

        start_t = time.monotonic()
        speech_duration = len(audio) / sample_rate
        try:
            # Transcribe directly from float32 array with domain priming & hotwords.
            # Note: vad_filter is False here because our outer VoiceActivityDetector has already cleanly segmented speech.
            # Running Silero VAD on top of an already sliced speech segment clips leading consonants (e.g. "write" -> "right").
            transcribe_kwargs: dict[str, Any] = {
                "beam_size": 5,
                "language": language if language and language != "auto" else None,
                "initial_prompt": ASSISTANT_DOMAIN_PROMPT,
                "condition_on_previous_text": False,
                "vad_filter": False,
                "no_speech_threshold": 0.50,
                "temperature": 0.0,
                "word_timestamps": True,
            }

            # If installed faster_whisper supports hotwords, pass domain hotwords
            import inspect
            sig_params = inspect.signature(self._model.transcribe).parameters
            if "hotwords" in sig_params:
                transcribe_kwargs["hotwords"] = ASSISTANT_HOTWORDS

            segments_gen, info = self._model.transcribe(audio, **transcribe_kwargs)

            raw_segments = list(segments_gen)
            elapsed = time.monotonic() - start_t

            if not raw_segments:
                logger.debug("FasterWhisper produced no segments (likely filtered as non-speech).")
                return TranscriptionResult(
                    text="",
                    confidence=0.0,
                    language=getattr(info, "language", language or "en"),
                    duration_seconds=elapsed,
                    speech_duration=speech_duration,
                    no_speech_prob=1.0,
                    provider_name=self.name,
                    raw_text="",
                    normalized_text="",
                )

            valid_texts: list[str] = []
            no_speech_probs: list[float] = []
            avg_logprobs: list[float] = []
            compression_ratios: list[float] = []
            word_tokens: list[dict[str, Any]] = []

            for seg in raw_segments:
                nsp = getattr(seg, "no_speech_prob", 0.0)
                alp = getattr(seg, "avg_logprob", 0.0)
                cr = getattr(seg, "compression_ratio", 1.0)
                txt = seg.text.strip()

                no_speech_probs.append(nsp)
                avg_logprobs.append(alp)
                compression_ratios.append(cr)

                # Segment-level validation: ignore pure non-speech noise or extreme compression repetition loops
                if nsp > 0.85 or cr > 3.2:
                    logger.debug("Discarding low-quality segment '%s' (nsp=%.2f, alp=%.2f, cr=%.2f)", txt, nsp, alp, cr)
                    continue

                if txt:
                    valid_texts.append(txt)

                # Collect word tokens
                words_list = getattr(seg, "words", None) or []
                for w in words_list:
                    word_tokens.append({
                        "word": getattr(w, "word", ""),
                        "start": getattr(w, "start", 0.0),
                        "end": getattr(w, "end", 0.0),
                        "probability": getattr(w, "probability", 1.0),
                    })

            full_text = " ".join(valid_texts).strip()

            mean_no_speech = float(np.mean(no_speech_probs)) if no_speech_probs else 0.0
            mean_avg_logprob = float(np.mean(avg_logprobs)) if avg_logprobs else 0.0
            max_comp_ratio = float(np.max(compression_ratios)) if compression_ratios else 1.0

            # Composite acoustic confidence score
            if mean_avg_logprob != 0.0:
                confidence = float(min(1.0, max(0.0, np.exp(mean_avg_logprob) * (1.0 - mean_no_speech))))
            else:
                confidence = float(getattr(info, "language_probability", 1.0))

            detected_lang = getattr(info, "language", language or "en")

            logger.info(
                "Transcribed audio (%.2fs) in %.2fs: '%s' (lang=%s, conf=%.2f, nsp=%.2f, alp=%.2f)",
                speech_duration,
                elapsed,
                full_text,
                detected_lang,
                confidence,
                mean_no_speech,
                mean_avg_logprob,
            )

            # Generate multi-candidate alternative hypotheses for downstream semantic evaluation
            alternatives = [full_text] if full_text else []
            if full_text:
                import re
                # Candidate A: Leading homophone variant ("Right" -> "Write")
                m_right = re.match(r"^(?:right|rite|wight)\b[,\s:;!.\-\?]*(.*)$", full_text, re.IGNORECASE)
                if m_right and m_right.group(1).strip():
                    alt_write = f"Write {m_right.group(1).strip()}"
                    if alt_write not in alternatives:
                        alternatives.append(alt_write)

                # Candidate B: Leading media distortion variant ("Le" / "Lay" -> "Play")
                m_media = re.match(r"^(?:le|lay|pla)\b[,\s:;!.\-\?]*(.*)$", full_text, re.IGNORECASE)
                if m_media and m_media.group(1).strip():
                    alt_play = f"Play {m_media.group(1).strip()}"
                    if alt_play not in alternatives:
                        alternatives.append(alt_play)

                # Candidate C: Phonetic entity normalization (e.g. Parwati -> Parvati)
                if "parwati" in full_text.lower():
                    alt_phon = re.sub(r"\bparwati\b", "Parvati", full_text, flags=re.IGNORECASE)
                    if alt_phon not in alternatives:
                        alternatives.append(alt_phon)

            return TranscriptionResult(
                text=full_text,
                confidence=confidence,
                language=detected_lang,
                duration_seconds=elapsed,
                speech_duration=speech_duration,
                no_speech_prob=mean_no_speech,
                avg_logprob=mean_avg_logprob,
                compression_ratio=max_comp_ratio,
                provider_name=self.name,
                raw_text=full_text,
                normalized_text=full_text.strip(),
                alternatives=alternatives,
                word_tokens=word_tokens,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_t
            logger.error("FasterWhisper transcription failed: %s", exc, exc_info=True)
            return TranscriptionResult(
                text="",
                confidence=0.0,
                duration_seconds=elapsed,
                speech_duration=speech_duration,
                provider_name=self.name,
                error=str(exc),
            )

    def shutdown(self) -> None:
        self._model = None
        self._initialized = False
        logger.info("FasterWhisperTranscriber shut down.")


class GroqCloudTranscriber(BaseTranscriber):
    """High-speed cloud speech transcriber powered by Groq's Whisper API."""

    def __init__(self, model: str = "whisper-large-v3-turbo") -> None:
        self.model = model
        self._client = None
        self._initialized = False

    @property
    def name(self) -> str:
        return f"groq_{self.model}"

    def initialize(self) -> None:
        if self._initialized and self._client is not None:
            return

        api_key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else None
        if not api_key:
            raise ValueError("GROQ_API_KEY is not configured for GroqCloudTranscriber.")

        from groq import Groq

        self._client = Groq(api_key=api_key)
        self._initialized = True
        logger.info("GroqCloudTranscriber initialized with model '%s'.", self.model)

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: str | None = None,
    ) -> TranscriptionResult:
        if not self._initialized or self._client is None:
            self.initialize()

        assert self._client is not None

        start_t = time.monotonic()
        speech_duration = len(audio) / sample_rate
        try:
            import soundfile as sf

            # Convert numpy float32 to WAV in-memory bytes
            wav_io = io.BytesIO()
            sf.write(wav_io, audio, sample_rate, format="WAV", subtype="PCM_16")
            wav_io.seek(0)
            wav_bytes = wav_io.read()

            file_tuple = ("audio.wav", wav_bytes, "audio/wav")

            transcription = self._client.audio.transcriptions.create(
                file=file_tuple,
                model=self.model,
                prompt=ASSISTANT_DOMAIN_PROMPT,
                language=language if language and language != "auto" else None,
                response_format="verbose_json",
                temperature=0.0,
            )

            text = getattr(transcription, "text", "").strip()
            elapsed = time.monotonic() - start_t

            # Extract segment metrics if verbose_json returned segments
            segments = getattr(transcription, "segments", None) or []
            no_speech_probs = [getattr(s, "no_speech_prob", 0.0) for s in segments if hasattr(s, "no_speech_prob")]
            avg_logprobs = [getattr(s, "avg_logprob", 0.0) for s in segments if hasattr(s, "avg_logprob")]
            compression_ratios = [getattr(s, "compression_ratio", 1.0) for s in segments if hasattr(s, "compression_ratio")]

            mean_no_speech = float(np.mean(no_speech_probs)) if no_speech_probs else 0.0
            mean_avg_logprob = float(np.mean(avg_logprobs)) if avg_logprobs else 0.0
            max_comp_ratio = float(np.max(compression_ratios)) if compression_ratios else 1.0

            if mean_avg_logprob != 0.0:
                confidence = float(min(1.0, max(0.0, np.exp(mean_avg_logprob) * (1.0 - mean_no_speech))))
            else:
                confidence = 1.0

            logger.info("Groq Cloud transcribed audio in %.2fs: '%s' (conf=%.2f)", elapsed, text, confidence)

            return TranscriptionResult(
                text=text,
                confidence=confidence,
                language=getattr(transcription, "language", language if language and language != "auto" else "auto"),
                duration_seconds=elapsed,
                speech_duration=speech_duration,
                no_speech_prob=mean_no_speech,
                avg_logprob=mean_avg_logprob,
                compression_ratio=max_comp_ratio,
                provider_name=self.name,
                raw_text=text,
                normalized_text=text,
                alternatives=[text] if text else [],
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_t
            logger.error("GroqCloudTranscriber failed: %s", exc)
            return TranscriptionResult(
                text="",
                confidence=0.0,
                duration_seconds=elapsed,
                speech_duration=speech_duration,
                provider_name=self.name,
                error=str(exc),
            )


    def shutdown(self) -> None:
        self._client = None
        self._initialized = False


class TranscriptionManager:
    """Coordinates active and fallback speech-to-text transcribers."""

    def __init__(
        self,
        primary_engine: str = "faster_whisper",
        model_size: str = "base",
        language: str = "auto",
    ) -> None:
        self.primary_engine = primary_engine
        self.model_size = model_size
        self.language = language

        self._transcribers: dict[str, BaseTranscriber] = {}
        self._active_transcriber: BaseTranscriber | None = None

    def initialize(self) -> None:
        """Construct and initialize the configured transcriber."""
        # Setup local faster-whisper transcriber
        local_transcriber = FasterWhisperTranscriber(model_size=self.model_size)
        self._transcribers["faster_whisper"] = local_transcriber

        # Setup cloud groq transcriber if key available
        if settings.groq_api_key and settings.groq_api_key.get_secret_value().strip():
            try:
                self._transcribers["groq"] = GroqCloudTranscriber()
            except Exception as e:
                logger.debug("Groq cloud transcriber not available: %s", e)

        if self.primary_engine in self._transcribers:
            self._active_transcriber = self._transcribers[self.primary_engine]
        else:
            self._active_transcriber = local_transcriber

        assert self._active_transcriber is not None
        self._active_transcriber.initialize()

    def transcribe(self, audio: np.ndarray, sample_rate: int = 16000) -> TranscriptionResult:
        """Transcribe the audio buffer using the active transcriber, with fallback if needed."""
        # Validation: Check that audio has non-trivial energy and length
        if len(audio) == 0:
            return TranscriptionResult(text="", error="Empty audio buffer")

        audio_duration = len(audio) / sample_rate
        if audio_duration < 0.2:
            return TranscriptionResult(text="", error="Audio too short (< 0.2s)")

        rms = float(np.sqrt(np.mean(audio ** 2)))
        if rms < 0.001:
            return TranscriptionResult(text="", error="Audio is pure silence")

        if self._active_transcriber is None:
            self.initialize()

        assert self._active_transcriber is not None
        result = self._active_transcriber.transcribe(
            audio,
            sample_rate=sample_rate,
            language=self.language,
        )

        # Fallback to local if cloud failed
        if not result.success and self._active_transcriber.name.startswith("groq"):
            local_engine = self._transcribers.get("faster_whisper")
            if local_engine:
                logger.warning("Cloud transcription failed. Falling back to local FasterWhisper.")
                result = local_engine.transcribe(audio, sample_rate=sample_rate, language=self.language)

        return result

    def shutdown(self) -> None:
        """Shut down all registered transcribers."""
        for name, transcriber in self._transcribers.items():
            try:
                transcriber.shutdown()
            except Exception as exc:
                logger.debug("Exception shutting down transcriber '%s': %s", name, exc)
        self._transcribers.clear()
        self._active_transcriber = None
        logger.info("TranscriptionManager shut down.")
