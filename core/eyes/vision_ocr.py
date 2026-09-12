"""Apple Vision native neural OCR and visual element localization on in-memory display frames.

Runs VNRecognizeTextRequest and VNClassifyImageRequest directly on RAM CVPixelBuffer / CGImage
with zero disk writes, mapping normalized bounding boxes accurately to Retina logical screen coordinates,
clustering product cards, prices, ratings, and semantic regions.
"""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field
from typing import Any

import Vision
Vision: Any = Vision
from core.eyes.accessibility import SemanticElement, UIElementType
from core.eyes.capture import DisplayMetrics, MemoryFrame
from core.logger import get_logger

logger = get_logger(__name__)


@dataclass
class VisualEntityCard:
    """A visually identified card or group (e.g. a product card on an e-commerce page)."""

    card_id: str
    title: str
    price: str = ""
    price_val: float = 0.0
    rating: str = ""
    rating_val: float = 0.0
    bounding_box: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    center_point: tuple[float, float] = (0.0, 0.0)
    elements: list[SemanticElement] = field(default_factory=list)
    specs: list[str] = field(default_factory=list)

    @property
    def x(self) -> float:
        return self.bounding_box[0]

    @property
    def y(self) -> float:
        return self.bounding_box[1]

    @property
    def width(self) -> float:
        return self.bounding_box[2]

    @property
    def height(self) -> float:
        return self.bounding_box[3]


class VisionOCR:
    """Local-first, neural text and visual perception using Apple's Vision framework."""

    def __init__(self, accurate: bool = False) -> None:
        self.accurate = accurate
        self._lock = threading.Lock()

    def recognize_text(self, frame: MemoryFrame) -> list[SemanticElement]:
        """Convenience alias for recognize_text_elements."""
        return self.recognize_text_elements(frame)

    def _create_handler_for_frame(self, frame: MemoryFrame) -> Any | None:
        """Create VNImageRequestHandler from in-memory pixel buffer or CGImage."""
        if frame is None:
            return None

        if frame.pixel_buffer is not None and hasattr(Vision.VNImageRequestHandler, "alloc"):
            try:
                handler = Vision.VNImageRequestHandler.alloc().initWithCVPixelBuffer_options_(
                    frame.pixel_buffer, {}
                )
                if handler:
                    return handler
            except Exception as exc:
                logger.debug("Failed to create handler from pixel_buffer: %s", exc)

        if frame.cg_image is not None and hasattr(Vision.VNImageRequestHandler, "alloc"):
            try:
                handler = Vision.VNImageRequestHandler.alloc().initWithCGImage_options_(
                    frame.cg_image, {}
                )
                if handler:
                    return handler
            except Exception as exc:
                logger.debug("Failed to create handler from cg_image: %s", exc)

        return None

    def recognize_text_elements(
        self,
        frame: MemoryFrame,
    ) -> list[SemanticElement]:
        """Extract localized text elements with exact screen coordinates from an in-memory frame."""
        handler = self._create_handler_for_frame(frame)
        if handler is None:
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

            success, error = handler.performRequests_error_([req], None)
            if not success or error:
                logger.debug("Vision OCR request failed: %s", error)
                return []

            observations = req.results() or []
            metrics = frame.metrics
            elements: list[SemanticElement] = []

            price_pattern = re.compile(
                r"(?:[\$₹€£]\s*\d+(?:[\.,]\d{2})?|\b\d+(?:[\.,]\d{2})?\s*(?:usd|inr|eur|rs\.?|dollars?|rupees?)\b)",
                re.IGNORECASE,
            )
            rating_pattern = re.compile(
                r"(?:\b[1-5](?:\.\d)?\s*(?:★|stars?|out of 5|\/5)\b)",
                re.IGNORECASE,
            )
            button_pattern = re.compile(
                r"^(?:search|submit|buy now|add to cart|login|sign in|sign up|ok|cancel|continue|download|done|save|close|next|prev|open|apply|filter|checkout)\b",
                re.IGNORECASE,
            )

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
                log_y = metrics.logical_y + (
                    (1.0 - bbox.origin.y - bbox.size.height) * metrics.logical_height
                )
                log_w = bbox.size.width * metrics.logical_width
                log_h = bbox.size.height * metrics.logical_height

                # Infer semantic type
                is_btn = bool(
                    button_pattern.search(text)
                    or (log_w < 180 and log_h < 45 and len(text.split()) <= 4 and conf > 0.6)
                )
                is_price = bool(price_pattern.search(text))
                is_rating = bool(rating_pattern.search(text))

                if is_btn:
                    elem_type = UIElementType.BUTTON
                    role = "OCRButton"
                else:
                    elem_type = UIElementType.TEXT
                    role = "OCRPrice" if is_price else ("OCRRating" if is_rating else "OCRText")

                metadata: dict[str, Any] = {}
                if is_price:
                    metadata["price"] = text
                if is_rating:
                    metadata["rating"] = text

                elem = SemanticElement.create(
                    element_id=f"ocr_{idx}_{text[:12]}",
                    element_type=elem_type,
                    label=text,
                    x=round(log_x, 1),
                    y=round(log_y, 1),
                    width=round(log_w, 1),
                    height=round(log_h, 1),
                    role=role,
                    value=text,
                    is_clickable=is_btn,
                    is_input=False,
                    source="vision_ocr",
                    confidence=conf,
                    metadata=metadata,
                )
                elements.append(elem)

            return elements

        except Exception as exc:
            logger.debug("Vision OCR exception: %s", exc)
            return []

    def classify_screen_content(self, frame: MemoryFrame) -> list[str]:
        """Perform on-device image scene/category classification using Apple Vision."""
        handler = self._create_handler_for_frame(frame)
        if handler is None:
            return []

        try:
            req = Vision.VNClassifyImageRequest.alloc().init()
            success, error = handler.performRequests_error_([req], None)
            if not success or error:
                return []

            results = req.results() or []
            tags: list[str] = []
            for r in results[:10]:
                c = float(r.confidence())
                if c >= 0.25:
                    tag = str(r.identifier() or "").lower()
                    if tag and tag not in tags:
                        tags.append(tag)
            return tags
        except Exception as exc:
            logger.debug("Vision scene classification exception: %s", exc)
            return []

    def detect_visual_cards(
        self,
        elements: list[SemanticElement],
    ) -> list[VisualEntityCard]:
        """Cluster nearby OCR text elements into candidate cards (e.g. product listings)."""
        price_re = re.compile(r"[\$₹€£]\s*(\d+(?:[\.,]\d{2})?)|\b(\d+(?:[\.,]\d{2})?)\s*(?:usd|inr|eur|rs)", re.I)
        cards: list[VisualEntityCard] = []

        # Find all elements that represent a price
        price_elems = [e for e in elements if e.metadata.get("price") or price_re.search(e.label)]
        if not price_elems:
            return []

        for idx, pe in enumerate(price_elems):
            px, py = pe.center_point
            # Search for title above or near the price (within 180px above or 50px below, 220px horizontally)
            neighbors = [
                e for e in elements
                if e != pe
                and abs(e.center_point[0] - px) < 220
                and -180 < (pe.center_point[1] - e.center_point[1]) < 80
            ]
            if not neighbors:
                continue

            # Candidate title is the longest text neighbor above the price
            title_candidates = [
                e for e in neighbors
                if e.y <= pe.y + 10 and len(e.label) > 5 and not price_re.search(e.label)
            ]
            title = title_candidates[0].label if title_candidates else "Product"

            # Check for rating neighbor
            rating_candidates = [e for e in neighbors if "★" in e.label or "out of 5" in e.label or "/5" in e.label]
            rating = rating_candidates[0].label if rating_candidates else ""

            # Parse numeric price value
            m = price_re.search(pe.label)
            val = 0.0
            if m:
                s = (m.group(1) or m.group(2) or "").replace(",", "")
                try:
                    val = float(s)
                except ValueError:
                    val = 0.0

            # Calculate bounding box encompassing the card elements
            all_card_elems = [pe] + neighbors
            min_x = min(e.x for e in all_card_elems)
            min_y = min(e.y for e in all_card_elems)
            max_r = max(e.x + e.width for e in all_card_elems)
            max_b = max(e.y + e.height for e in all_card_elems)
            bw = max_r - min_x
            bh = max_b - min_y

            cards.append(
                VisualEntityCard(
                    card_id=f"card_{idx + 1}",
                    title=title,
                    price=pe.label,
                    price_val=val,
                    rating=rating,
                    bounding_box=(min_x, min_y, bw, bh),
                    center_point=(min_x + bw / 2.0, min_y + bh / 2.0),
                    elements=all_card_elems,
                )
            )

        return cards

    @staticmethod
    def extract_full_text(elements: list[SemanticElement]) -> list[str]:
        """Extract sorted list of visible text lines from detected OCR elements."""
        sorted_elems = sorted(elements, key=lambda e: (e.y, e.x))
        lines: list[str] = []
        for e in sorted_elems:
            lbl = e.label.strip()
            if lbl and lbl not in lines:
                lines.append(lbl)
        return lines
