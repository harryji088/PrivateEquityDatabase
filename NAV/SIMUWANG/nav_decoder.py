"""Decode image-rendered Simuwang NAV values without executing site code."""

from __future__ import annotations

import base64
import hashlib
import io
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import DefaultDict, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from PIL import Image


NAV_QUANT = Decimal("0.0001")
PCT_QUANT = Decimal("0.01")
CALIBRATION_ROW_LIMIT = 50
NAV_RE = re.compile(r"^\d+(?:\.\d+)?$")


class DecodeError(RuntimeError):
    """Raised when image NAVs cannot be decoded or validated reliably."""


@dataclass
class Glyph:
    mask: np.ndarray

    @property
    def signature(self) -> str:
        digest = hashlib.sha1()
        digest.update("{}x{}:".format(*self.mask.shape).encode("ascii"))
        digest.update(self.mask.tobytes())
        return digest.hexdigest()


def _dark_mask(image: Image.Image) -> np.ndarray:
    rgba = np.asarray(image.convert("RGBA"))
    alpha = rgba[:, :, 3] > 0
    luminance = rgba[:, :, :3].astype(np.float32).mean(axis=2)
    return alpha & (luminance < 180)


def _segment_mask(mask: np.ndarray) -> List[Glyph]:
    glyphs: List[Glyph] = []
    occupied = mask.any(axis=0)
    start: Optional[int] = None

    for x, is_occupied in enumerate(occupied):
        if is_occupied and start is None:
            start = x
        at_end = x == len(occupied) - 1
        if start is not None and (not is_occupied or at_end):
            end = x if is_occupied and at_end else x - 1
            piece = mask[:, start : end + 1]
            occupied_rows = np.flatnonzero(piece.any(axis=1))
            if occupied_rows.size:
                piece = piece[occupied_rows[0] : occupied_rows[-1] + 1]
                height, width = piece.shape
                # Site glyphs are about 34 px high. A decimal point is 5x5.
                # Ignore transparent/white anti-scraping noise between them.
                if height >= 25 or (height <= 8 and width >= 2):
                    glyphs.append(Glyph(piece.copy()))
            start = None

    return glyphs


def data_urls_to_glyphs(sources: Sequence[str]) -> List[Glyph]:
    glyphs: List[Glyph] = []
    for source in sources:
        if "," not in source or "base64" not in source[:80]:
            continue
        try:
            payload = base64.b64decode(source.split(",", 1)[1], validate=False)
            image = Image.open(io.BytesIO(payload))
        except Exception as exc:
            raise DecodeError("Invalid NAV image payload") from exc
        glyphs.extend(_segment_mask(_dark_mask(image)))
    return glyphs


def _normalize_mask(mask: np.ndarray) -> np.ndarray:
    target_height = 38
    target_width = 28
    usable_height = 34
    usable_width = 24
    height, width = mask.shape
    scale = min(usable_height / float(height), usable_width / float(width))
    resized_width = max(1, int(round(width * scale)))
    resized_height = max(1, int(round(height * scale)))
    image = Image.fromarray((mask.astype(np.uint8) * 255))
    image = image.resize((resized_width, resized_height), Image.Resampling.NEAREST)
    resized = np.asarray(image) > 0
    canvas = np.zeros((target_height, target_width), dtype=bool)
    top = (target_height - resized_height) // 2
    left = (target_width - resized_width) // 2
    canvas[top : top + resized_height, left : left + resized_width] = resized
    return canvas


def _mask_distance(left: np.ndarray, right: np.ndarray) -> float:
    union = np.logical_or(left, right).sum()
    if not union:
        return 0.0
    intersection = np.logical_and(left, right).sum()
    return 1.0 - float(intersection) / float(union)


class GlyphClassifier:
    def __init__(self) -> None:
        self._votes: DefaultDict[str, Counter[str]] = defaultdict(Counter)
        self._glyphs: Dict[str, Glyph] = {}
        self._exact: Dict[str, str] = {}
        self._templates: DefaultDict[str, List[np.ndarray]] = defaultdict(list)

    def observe(self, glyphs: Sequence[Glyph], expected: str) -> bool:
        if len(glyphs) != len(expected):
            return False
        for glyph, character in zip(glyphs, expected):
            if character not in "0123456789.":
                continue
            signature = glyph.signature
            self._votes[signature][character] += 1
            self._glyphs[signature] = glyph
        return True

    def finalize(self) -> None:
        self._exact.clear()
        self._templates.clear()
        for signature, votes in self._votes.items():
            character, count = votes.most_common(1)[0]
            total = sum(votes.values())
            # Reconstructing a four-decimal NAV from a displayed two-decimal
            # return can differ in the last digit. Keep the majority mapping;
            # the full decoded series is validated against every displayed
            # period return before it is accepted.
            if count / float(total) < 0.50:
                continue
            self._exact[signature] = character
            self._templates[character].append(
                _normalize_mask(self._glyphs[signature].mask)
            )
        if not self._exact:
            raise DecodeError("No reliable digit templates could be learned")

    @property
    def known_characters(self) -> str:
        return "".join(sorted(self._templates))

    def classify(self, glyph: Glyph) -> Tuple[str, float]:
        exact = self._exact.get(glyph.signature)
        if exact is not None:
            return exact, 0.0

        normalized = _normalize_mask(glyph.mask)
        candidates: List[Tuple[float, str]] = []
        for character, templates in self._templates.items():
            best = min(_mask_distance(normalized, template) for template in templates)
            candidates.append((best, character))
        if not candidates:
            raise DecodeError("Digit classifier has no templates")
        candidates.sort()
        distance, character = candidates[0]
        margin = candidates[1][0] - distance if len(candidates) > 1 else 1.0
        if distance > 0.22 or (distance > 0.08 and margin < 0.025):
            raise DecodeError(
                "Unknown NAV glyph (distance {:.3f}, known {})".format(
                    distance, self.known_characters
                )
            )
        return character, distance

    def decode(self, glyphs: Sequence[Glyph]) -> str:
        if not glyphs:
            return ""
        value = "".join(self.classify(glyph)[0] for glyph in glyphs)
        if not NAV_RE.match(value):
            raise DecodeError("Decoded NAV is not numeric: {}".format(value))
        return value


def parse_percentage(value: str) -> Decimal:
    cleaned = value.strip().replace("%", "").replace("+", "")
    try:
        return Decimal(cleaned)
    except InvalidOperation as exc:
        raise DecodeError("Invalid percentage: {}".format(value)) from exc


def latest_nav_from_return(return_percentage: str) -> Decimal:
    value = Decimal("1") + parse_percentage(return_percentage) / Decimal("100")
    return value.quantize(NAV_QUANT, rounding=ROUND_HALF_UP)


def reconstruct_reinvested_navs(
    changes: Sequence[str], latest_nav: Decimal
) -> List[Decimal]:
    values: List[Decimal] = []
    current = latest_nav.quantize(NAV_QUANT, rounding=ROUND_HALF_UP)
    for change in changes:
        values.append(current)
        rate = parse_percentage(change) / Decimal("100")
        denominator = Decimal("1") + rate
        if denominator <= 0:
            raise DecodeError("Invalid NAV change: {}".format(change))
        current = (current / denominator).quantize(
            NAV_QUANT, rounding=ROUND_HALF_UP
        )
    return values


def format_nav(value: Decimal) -> str:
    return format(value.quantize(NAV_QUANT, rounding=ROUND_HALF_UP), ".4f")


def _validate_changes(rows: Sequence[Dict[str, str]]) -> None:
    mismatches: List[str] = []
    for index in range(len(rows) - 1):
        current = Decimal(rows[index]["cumulative_nav_reinvest"])
        previous = Decimal(rows[index + 1]["cumulative_nav_reinvest"])
        calculated = ((current / previous - Decimal("1")) * Decimal("100")).quantize(
            PCT_QUANT, rounding=ROUND_HALF_UP
        )
        displayed = parse_percentage(rows[index]["change_pct"]).quantize(
            PCT_QUANT, rounding=ROUND_HALF_UP
        )
        if calculated != displayed:
            mismatches.append(
                "{}: decoded {}%, displayed {}%".format(
                    rows[index]["date"], calculated, displayed
                )
            )
    allowed = max(1, int(len(rows) * 0.02))
    if len(mismatches) > allowed:
        raise DecodeError(
            "Decoded NAV change validation failed: {}".format("; ".join(mismatches[:5]))
        )


def decode_nav_rows(
    raw_rows: Sequence[Dict[str, object]], latest_nav: Decimal
) -> List[Dict[str, str]]:
    if not raw_rows:
        raise DecodeError("No historical NAV rows were found")

    calibration_count = min(CALIBRATION_ROW_LIMIT, len(raw_rows))
    changes = [str(row.get("change_pct", "")) for row in raw_rows]
    calibration = reconstruct_reinvested_navs(
        changes[:calibration_count], latest_nav
    )
    classifier = GlyphClassifier()
    training_rows = 0

    glyph_rows: List[List[List[Glyph]]] = []
    for index, raw in enumerate(raw_rows):
        nav_cells = raw.get("nav_cells")
        if not isinstance(nav_cells, list) or len(nav_cells) != 3:
            raise DecodeError("Unexpected NAV table column structure")
        cells = [data_urls_to_glyphs(list(cell)) for cell in nav_cells]
        glyph_rows.append(cells)
        if index < calibration_count and classifier.observe(
            cells[1], format_nav(calibration[index])
        ):
            training_rows += 1

    if training_rows < min(3, calibration_count):
        raise DecodeError(
            "Too few rows matched the cumulative NAV calibration ({}/{})".format(
                training_rows, calibration_count
            )
        )
    classifier.finalize()

    decoded: List[Dict[str, str]] = []
    for index, (raw, cells) in enumerate(zip(raw_rows, glyph_rows)):
        values = [classifier.decode(cell) for cell in cells]
        if not all(values):
            raise DecodeError("A NAV cell is empty on {}".format(raw.get("date", "")))
        row = {
            "date": str(raw.get("date", "")),
            "unit_nav": values[0],
            "cumulative_nav_reinvest": values[1],
            "cumulative_nav_no_reinvest": values[2],
            "change_pct": str(raw.get("change_pct", "")),
        }
        decoded.append(row)

    if decoded[0]["cumulative_nav_reinvest"] != format_nav(latest_nav):
        raise DecodeError(
            "Decoded latest cumulative NAV disagrees with the page anchor"
        )
    _validate_changes(decoded)
    return decoded
