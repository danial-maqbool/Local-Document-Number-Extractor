"""
Local Document Number Extractor - Confidence & Status Evaluation Service
Calculates multi-factor confidence and determines overall document extraction status.
"""
from typing import Dict, List
from backend.models.schemas import (
    ExtractedFieldResult, QualityReport, QualityStatus, ExtractionStatus
)

class ConfidenceService:

    @classmethod
    def calculate_overall_confidence(
        cls,
        fields: Dict[str, ExtractedFieldResult],
        quality: QualityReport
    ) -> float:
        """
        Calculate overall document confidence:
        - Weighted average of field confidences
        - Quality penalty if image had blur / contrast warnings
        """
        if not fields:
            return 0.0

        field_scores = [f.confidence for f in fields.values()]
        avg_score = sum(field_scores) / float(len(field_scores))

        # Apply image quality factor
        quality_penalty = 1.0
        if quality.status == QualityStatus.REVIEW:
            quality_penalty = 0.90
        elif quality.status == QualityStatus.LOW_QUALITY:
            quality_penalty = 0.75
        elif quality.status == QualityStatus.FAILED:
            quality_penalty = 0.50

        overall = round(min(1.0, max(0.0, avg_score * quality_penalty)), 4)
        return overall

    @classmethod
    def determine_document_status(
        cls,
        fields: Dict[str, ExtractedFieldResult],
        quality: QualityReport,
        cross_field_passed: bool,
        overall_confidence: float
    ) -> ExtractionStatus:
        """
        Determine if document is Good, Review, or Failed.
        Conditions for REVIEW:
        - Image quality is REVIEW or LOW_QUALITY
        - Any required field is missing or invalid
        - Any field confidence < threshold
        - Cross-field validation failed
        - Ambiguity detected
        """
        if quality.status == QualityStatus.FAILED:
            return ExtractionStatus.FAILED

        # Check if all fields valid
        all_valid = all(f.is_valid for f in fields.values())
        has_ambiguity = any(
            any("AMBIGUOUS" in note for note in f.validation_notes)
            for f in fields.values()
        )

        if not all_valid or not cross_field_passed or has_ambiguity or quality.status != QualityStatus.GOOD:
            return ExtractionStatus.REVIEW

        if overall_confidence < 0.70:
            return ExtractionStatus.REVIEW

        return ExtractionStatus.GOOD
