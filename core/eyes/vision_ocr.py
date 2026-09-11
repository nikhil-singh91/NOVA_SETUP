"""Apple Vision native neural OCR and visual text localization on in-memory display frames.

Runs VNRecognizeTextRequest directly on RAM CGImage buffers with zero disk writes,
mapping normalized bounding boxes accurately to Retina logical screen coordinates.
"""

from __future__ import annotations

import re
import threading
from typing import Any

import Vision
from core.eyes.accessibility import SemanticElement, UIElementType
from core.eyes.capture import DisplayMetrics, MemoryFrame
from core.logger import get_logger

logger = get_logger(__name__)


class VisionOCR:
    """Local-first, neural text recognition using Apple's Vision framework."""

    def __init__(self, accurate: bool = False) -> None:
        self.accurate = accurate
        self._lock = threading.Lock()

    def recognize_text(self, frame: MemoryFrame) -> list[SemanticElement]:
        """Convenience alias for recognize_text_elements."""
        return self.recognize_text_elements(frame)

    def recognize_text_elements(
        self,
        frame: MemoryFrame,
    ) -> list[SemanticElement]:
        """Extract localized text elements with exact screen coordinates from an in-memory frame."""
        if frame is None or frame.cg_image is None:
            return []

        try:
            req = Vision.VNRecognizeTextRequest.alloc().init()
            level = (
                Vision.VNRequestTextRecognitionLevelAccurate
                if self.accurate
                else Vision.VNRequestTextRecognitionLevelFast
            )
            req.setRecognitionLevel_(level)
            req.setUsesLanguageCorrection_(True)

            handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
                frame.cg_image, {}
            )
            success, error = handler.performRequests_error_([req], None)
            if not success or error:
                logger.debug("Vision OCR request failed: %s", error)
                return []

            observations = req.results() or []
            metrics = frame.metrics
            elements: list[SemanticElement] = []

            for idx, obs in enumerate(observations):
                top_candidates = obs.topCandidates_(1)
                if not top_candidates:
                    continue

                candidate = top_candidates[0]
                text = str(candidate.string() or "").strip()
                if not text:
                    continue

                conf = float(candidate.confidence())
                bbox = obs.boundingBox()

                # Coordinate transformation: Vision (bottom-left 0..1) -> Logical screen (top-left)
                log_x = metrics.logical_x + (bbox.origin.x * metrics.logical_width)
                log_y = metrics.logical_y + ((1.0 - bbox.origin.y - bbox.size.height) * metrics.logical_height)
                log_w = bbox.size.width * metrics.logical_width
                log_h = bbox.size.height * metrics.logical_height

                # Determine if text is likely clickable or a button based on keywords or geometry
                is_click = bool(
                    re.search(r"^(?:search|submit|login|sign in|sign up|ok|cancel|continue|download|done|save|close|next|prev|open)\b", text, re.IGNORECASE)
                    or (log_w < 160 and log_h < 45 and len(text.split()) <= 3)
                )

                elem_type = UIElementType.BUTTON if is_click else UIElementType.TEXT

                elem = SemanticElement.create(
                    element_id=f"ocr_{idx}_{text[:12]}",
                    element_type=elem_type,
                    label=text,
                    x=round(log_x, 1),
                    y=round(log_y, 1),
                    width=round(log_w, 1),
                    height=round(log_h, 1),
                    role="OCRText",
                    value=text,
                    is_clickable=is_click,
                    is_input=False,
                    source="vision_ocr",
                    confidence=conf,
                )
                elements.append(elem)

            return elements

        except Exception as exc:
            logger.debug("Vision OCR exception: %s", exc)
            return []

    @staticmethod
    def extract_full_text(elements: list[SemanticElement]) -> list[str]:
        """Extract sorted list of visible text lines from detected OCR elements."""
        # Sort spatially top-to-bottom, left-to-right
        sorted_elems = sorted(elements, key=lambda e: (e.y, e.x))
        lines: list[str] = []
        for e in sorted_elems:
            lbl = e.label.strip()
            if lbl and lbl not in lines:
                lines.append(lbl)
        return lines
