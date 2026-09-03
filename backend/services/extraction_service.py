"""
Local Document Number Extractor - Multi-Strategy Field Extraction & Candidate Ranking
Implements Methods A, B, C, D, E with auditability, fuzzy matching, and ambiguity detection.
"""
import re
import math
import logging
from difflib import SequenceMatcher
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np

from backend.config import DEFAULT_CONFIDENCE_THRESHOLD, AMBIGUITY_DELTA_THRESHOLD
from backend.models.schemas import (
    FieldDefinition, FieldType, DocumentTemplate, RegionCoords,
    ExtractionCandidate, ExtractedFieldResult, ExtractionMethod
)
from backend.services.ocr_service import OCRItem, OCRService

logger = logging.getLogger("extractor.extraction")

class ExtractionService:

    @staticmethod
    def fuzzy_match(s1: str, s2: str) -> float:
        """Compute string similarity ratio between 0.0 and 1.0"""
        s1_clean = re.sub(r"[^\w\s]", "", s1).strip().lower()
        s2_clean = re.sub(r"[^\w\s]", "", s2).strip().lower()
        if not s1_clean or not s2_clean:
            return 0.0
        if s1_clean == s2_clean or s1_clean in s2_clean or s2_clean in s1_clean:
            return 1.0
        return SequenceMatcher(None, s1_clean, s2_clean).ratio()

    @classmethod
    def find_label_matches(
        cls,
        field: FieldDefinition,
        ocr_items: List[OCRItem]
    ) -> List[Tuple[OCRItem, float]]:
        """
        Find OCR items that match any English or Urdu label aliases for the field.
        Returns list of (OCRItem, match_confidence).
        """
        all_labels = field.labels + field.urdu_labels
        matches = []
        for item in ocr_items:
            best_score = 0.0
            for label in all_labels:
                score = cls.fuzzy_match(label, item.text)
                if score > best_score:
                    best_score = score
            if best_score >= 0.70:
                matches.append((item, best_score))

        matches.sort(key=lambda x: x[1], reverse=True)
        return matches

    @staticmethod
    def parse_numeric_candidate(
        raw_text: str,
        field_type: FieldType,
        decimal_allowed: bool = False
    ) -> Optional[Union[int, float, str]]:
        """
        Parse raw text into typed numeric candidate (integer or decimal or code/date).
        Normalizes OCR character substitutions.
        """
        cleaned, _ = OCRService.normalize_numeric_string(raw_text)

        if field_type == FieldType.DECIMAL or decimal_allowed:
            # Match decimal patterns like 1,234.56 or 1234.56 or 1234
            match = re.search(r"[-+]?\d+(?:[,\.]\d+)?", cleaned)
            if match:
                num_str = match.group(0).replace(",", "")
                # If there are multiple periods, keep the last
                if num_str.count(".") > 1:
                    parts = num_str.split(".")
                    num_str = "".join(parts[:-1]) + "." + parts[-1]
                try:
                    return round(float(num_str), 2)
                except ValueError:
                    pass
        elif field_type == FieldType.INTEGER:
            # Match pure digit sequences
            digits = re.findall(r"\d+", cleaned)
            if digits:
                # Combine or pick longest sequence
                longest = max(digits, key=len)
                try:
                    return int(longest)
                except ValueError:
                    pass
        elif field_type == FieldType.DATE:
            # Match date patterns like DD-MM-YYYY, YYYY-MM-DD, DD/MM/YYYY
            date_match = re.search(r"\b(?:\d{2,4}[-\/\.]\d{1,2}[-\/\.]\d{2,4})\b", cleaned)
            if date_match:
                return date_match.group(0)
        elif field_type == FieldType.PHONE:
            phone_match = re.search(r"\b(?:\+?\d{1,3}[- ]?)?(?:\d{10,12})\b", cleaned)
            if phone_match:
                return phone_match.group(0)
        elif field_type == FieldType.CODE:
            code_match = re.search(r"\b[A-Za-z0-9\-_]{4,20}\b", cleaned)
            if code_match:
                return code_match.group(0)

        # Fallback digit extraction
        digits_only = re.sub(r"[^\d]", "", cleaned)
        if digits_only:
            try:
                return int(digits_only)
            except ValueError:
                return digits_only

        return None

    @staticmethod
    def bbox_distance(box1: List[int], box2: List[int]) -> float:
        """Euclidean distance between center points of two bounding boxes"""
        c1 = (box1[0] + box1[2] / 2.0, box1[1] + box1[3] / 2.0)
        c2 = (box2[0] + box2[2] / 2.0, box2[1] + box2[3] / 2.0)
        return math.hypot(c1[0] - c2[0], c1[1] - c2[1])

    @staticmethod
    def is_box_inside_region(norm_bbox: List[float], region: RegionCoords) -> bool:
        """Check if an item's normalized bounding box overlaps with expected page region"""
        x_min, y_min, x_max, y_max = norm_bbox
        # Overlap check
        overlap_x = max(0.0, min(x_max, region.x_max) - max(x_min, region.x_min))
        overlap_y = max(0.0, min(y_max, region.y_max) - max(y_min, region.y_min))
        box_area = (x_max - x_min) * (y_max - y_min)
        if box_area <= 0:
            return False
        overlap_area = overlap_x * overlap_y
        return (overlap_area / box_area) >= 0.25

    @classmethod
    def extract_field_candidates(
        cls,
        field: FieldDefinition,
        ocr_items: List[OCRItem],
        img_width: int,
        img_height: int
    ) -> List[ExtractionCandidate]:
        """
        Detect candidate numeric values for a field using Methods A, B, C, D.
        """
        candidates: List[ExtractionCandidate] = []
        numeric_items = [it for it in ocr_items if it.is_numeric]
        label_matches = cls.find_label_matches(field, ocr_items)

        # Method A: Fixed Region Extraction
        if field.region:
            for item in numeric_items:
                if cls.is_box_inside_region(item.norm_bbox, field.region):
                    parsed = cls.parse_numeric_candidate(item.text, field.type, field.decimal_allowed)
                    if parsed is not None:
                        candidates.append(ExtractionCandidate(
                            field_name=field.name,
                            raw_value=item.text,
                            normalized_value=parsed,
                            ocr_confidence=item.confidence,
                            field_confidence=0.85 * item.confidence,
                            bbox=item.bbox,
                            method=ExtractionMethod.FIXED_REGION,
                            audit_notes=f"Located in defined template region {field.region.dict()}"
                        ))

        # Method B: Label Proximity (Right, Below, Nearest)
        for label_item, label_score in label_matches:
            lx, ly, lw, lh = label_item.bbox
            for num_item in numeric_items:
                if num_item.text == label_item.text:
                    continue

                nx, ny, nw, nh = num_item.bbox
                parsed = cls.parse_numeric_candidate(num_item.text, field.type, field.decimal_allowed)
                if parsed is None:
                    continue

                # Case B1: Right of label (same line: |ny - ly| < lh * 1.2 and nx >= lx)
                if abs(ny - ly) < lh * 1.5 and nx >= lx and (nx - (lx + lw)) < img_width * 0.45:
                    candidates.append(ExtractionCandidate(
                        field_name=field.name,
                        raw_value=num_item.text,
                        normalized_value=parsed,
                        ocr_confidence=num_item.confidence,
                        field_confidence=0.90 * label_score * num_item.confidence,
                        bbox=num_item.bbox,
                        method=ExtractionMethod.LABEL_PROXIMITY_RIGHT,
                        audit_notes=f"Found right of label '{label_item.text}' (dist {nx - (lx + lw)}px)"
                    ))
                # Case B2: Below label (nx within label x-span, ny > ly)
                elif ny > ly and (ny - (ly + lh)) < img_height * 0.15 and abs(nx - lx) < lw * 1.5:
                    candidates.append(ExtractionCandidate(
                        field_name=field.name,
                        raw_value=num_item.text,
                        normalized_value=parsed,
                        ocr_confidence=num_item.confidence,
                        field_confidence=0.85 * label_score * num_item.confidence,
                        bbox=num_item.bbox,
                        method=ExtractionMethod.LABEL_PROXIMITY_BELOW,
                        audit_notes=f"Found below label '{label_item.text}' (vertical dist {ny - (ly + lh)}px)"
                    ))
                # Case B3: Nearest radial proximity
                dist = cls.bbox_distance(label_item.bbox, num_item.bbox)
                if dist < img_width * 0.35:
                    proximity_factor = max(0.5, 1.0 - (dist / (img_width * 0.35)))
                    candidates.append(ExtractionCandidate(
                        field_name=field.name,
                        raw_value=num_item.text,
                        normalized_value=parsed,
                        ocr_confidence=num_item.confidence,
                        field_confidence=0.80 * label_score * num_item.confidence * proximity_factor,
                        bbox=num_item.bbox,
                        method=ExtractionMethod.LABEL_PROXIMITY_NEAREST,
                        audit_notes=f"Radial proximity to '{label_item.text}' (dist {int(dist)}px)"
                    ))

        # Method C: Regex Pattern Matching
        if field.regex_pattern:
            try:
                pattern = re.compile(field.regex_pattern)
                for item in ocr_items:
                    cleaned, _ = OCRService.normalize_numeric_string(item.text)
                    m = pattern.search(cleaned)
                    if m:
                        matched_str = m.group(0)
                        parsed = cls.parse_numeric_candidate(matched_str, field.type, field.decimal_allowed)
                        if parsed is not None:
                            candidates.append(ExtractionCandidate(
                                field_name=field.name,
                                raw_value=item.text,
                                normalized_value=parsed,
                                ocr_confidence=item.confidence,
                                field_confidence=0.92 * item.confidence,
                                bbox=item.bbox,
                                method=ExtractionMethod.PATTERN_REGEX,
                                audit_notes=f"Matched regex pattern {field.regex_pattern}"
                            ))
            except re.error as e:
                logger.error(f"Invalid regex for field {field.name}: {e}")

        # Remove duplicate candidates with identical normalized value and bbox
        unique_candidates: List[ExtractionCandidate] = []
        seen = set()
        for cand in candidates:
            key = (str(cand.normalized_value), cand.bbox[0], cand.bbox[1])
            if key not in seen:
                seen.add(key)
                unique_candidates.append(cand)

        return unique_candidates

    @classmethod
    def rank_candidates(
        cls,
        field: FieldDefinition,
        candidates: List[ExtractionCandidate],
        img_width: int,
        img_height: int
    ) -> ExtractedFieldResult:
        """
        Method E: Candidate Ranking & Ambiguity Resolution
        Scores each candidate based on:
        - OCR confidence
        - Digit count conformance
        - Range validity (min_value, max_value)
        - Region match
        - Extraction method priority
        """
        if not candidates:
            return ExtractedFieldResult(
                field_name=field.name,
                value=None,
                raw_value=None,
                confidence=0.0,
                bbox=None,
                method=None,
                is_valid=False,
                validation_notes=["Field value not found in document"],
                candidates=[]
            )

        scored_candidates = []
        for cand in candidates:
            score = cand.field_confidence
            rejection_reasons = []

            val_str = str(cand.normalized_value).replace(".", "").replace("-", "")
            digit_count = len(re.sub(r"\D", "", val_str))

            # Digit count penalty / boost
            if field.min_digits is not None and digit_count < field.min_digits:
                rejection_reasons.append(f"Digit count {digit_count} < min {field.min_digits}")
                score *= 0.4
            elif field.max_digits is not None and digit_count > field.max_digits:
                rejection_reasons.append(f"Digit count {digit_count} > max {field.max_digits}")
                score *= 0.4
            elif field.min_digits is not None and field.max_digits is not None:
                # Perfect match inside range
                score *= 1.15

            # Numerical range validation
            if isinstance(cand.normalized_value, (int, float)):
                num_val = float(cand.normalized_value)
                if field.min_value is not None and num_val < field.min_value:
                    rejection_reasons.append(f"Value {num_val} < min allowed {field.min_value}")
                    score *= 0.3
                if field.max_value is not None and num_val > field.max_value:
                    rejection_reasons.append(f"Value {num_val} > max allowed {field.max_value}")
                    score *= 0.3

            # Prefer LABEL_PROXIMITY_RIGHT and FIXED_REGION
            if cand.method == ExtractionMethod.LABEL_PROXIMITY_RIGHT:
                score *= 1.10
            elif cand.method == ExtractionMethod.FIXED_REGION:
                score *= 1.05

            score = min(1.0, max(0.0, round(score, 4)))
            cand.field_confidence = score
            cand.rejection_reason = "; ".join(rejection_reasons) if rejection_reasons else None
            scored_candidates.append(cand)

        # Sort by compound field confidence descending
        scored_candidates.sort(key=lambda c: c.field_confidence, reverse=True)

        best_cand = scored_candidates[0]
        notes = []

        # Ambiguity check: Compare top candidate with second candidate
        is_ambiguous = False
        if len(scored_candidates) > 1:
            second_cand = scored_candidates[1]
            if (
                best_cand.normalized_value != second_cand.normalized_value
                and abs(best_cand.field_confidence - second_cand.field_confidence) < AMBIGUITY_DELTA_THRESHOLD
                and best_cand.field_confidence >= 0.50
            ):
                is_ambiguous = True
                notes.append(
                    f"AMBIGUOUS: Competing candidate '{second_cand.normalized_value}' "
                    f"has score {second_cand.field_confidence:.2f} within delta {AMBIGUITY_DELTA_THRESHOLD}."
                )

        best_cand.is_selected = True
        is_valid = (
            best_cand.field_confidence >= field.confidence_threshold
            and not is_ambiguous
            and not best_cand.rejection_reason
        )

        if best_cand.rejection_reason:
            notes.append(f"Validation issue: {best_cand.rejection_reason}")

        return ExtractedFieldResult(
            field_name=field.name,
            value=best_cand.normalized_value,
            raw_value=best_cand.raw_value,
            confidence=best_cand.field_confidence,
            bbox=best_cand.bbox,
            method=best_cand.method,
            is_valid=is_valid,
            is_manual=False,
            validation_notes=notes,
            candidates=scored_candidates
        )
