import pytest
from backend.models.schemas import (
    FieldDefinition, FieldType, DocumentTemplate, RegionCoords,
    CrossFieldRule, ExtractionMethod, QualityReport, QualityStatus,
    ExtractionStatus, ExtractedFieldResult
)
from backend.services.ocr_service import OCRItem
from backend.services.extraction_service import ExtractionService
from backend.services.validation_service import ValidationService
from backend.services.confidence_service import ConfidenceService

def test_fuzzy_matching():
    assert ExtractionService.fuzzy_match("Account Number", "Account No.") > 0.70
    assert ExtractionService.fuzzy_match("Current Reading", "Current Read") > 0.70
    assert ExtractionService.fuzzy_match("Consumer ID", "Different Thing") < 0.50

def test_label_proximity_right_extraction():
    field = FieldDefinition(
        name="Account Number",
        type=FieldType.INTEGER,
        labels=["Account No", "Account Number"],
        min_digits=8,
        max_digits=12,
        required=True
    )
    # Simulate OCR items: label at (50, 100, 120, 25), number to its right at (200, 100, 100, 25)
    ocr_items = [
        OCRItem(text="Account No:", confidence=0.98, bbox=[50, 100, 120, 25], norm_bbox=[0.1, 0.2, 0.25, 0.25], is_numeric=False),
        OCRItem(text="123456789", confidence=0.95, bbox=[200, 100, 100, 25], norm_bbox=[0.3, 0.2, 0.45, 0.25], is_numeric=True),
    ]

    cands = ExtractionService.extract_field_candidates(field, ocr_items, img_width=800, img_height=1000)
    assert len(cands) >= 1
    assert cands[0].normalized_value == 123456789
    assert cands[0].method == ExtractionMethod.LABEL_PROXIMITY_RIGHT

    result = ExtractionService.rank_candidates(field, cands, img_width=800, img_height=1000)
    assert result.value == 123456789
    assert result.is_valid is True
    assert result.confidence > 0.75

def test_cross_field_units_validation():
    template = DocumentTemplate(
        id="test_template",
        name="Test",
        fields=[],
        cross_field_rules=[
            CrossFieldRule(
                rule_name="units_check",
                description="Units check",
                rule_type="difference_equals",
                target_field="Units",
                operands=["Current Reading", "Previous Reading"],
                tolerance=0.01
            )
        ]
    )

    # Consistent fields: 1500 - 1000 = 500
    fields_valid = {
        "Previous Reading": ExtractedFieldResult(
            field_name="Previous Reading", value=1000, confidence=0.95, is_valid=True
        ),
        "Current Reading": ExtractedFieldResult(
            field_name="Current Reading", value=1500, confidence=0.95, is_valid=True
        ),
        "Units": ExtractedFieldResult(
            field_name="Units", value=500, confidence=0.95, is_valid=True
        )
    }

    passed, errors = ValidationService.validate_cross_fields(template, fields_valid)
    assert passed is True
    assert len(errors) == 0

    # Inconsistent fields: Current = 1200, Prev = 1000, Units = 500 (1200 - 1000 = 200 != 500)
    fields_invalid = dict(fields_valid)
    fields_invalid["Current Reading"] = ExtractedFieldResult(
        field_name="Current Reading", value=1200, confidence=0.95, is_valid=True
    )

    passed, errors = ValidationService.validate_cross_fields(template, fields_invalid)
    assert passed is False
    assert len(errors) == 1

def test_confidence_and_status():
    quality = QualityReport(
        blur_score=120.0, brightness=110.0, contrast=50.0,
        width=800, height=1000, status=QualityStatus.GOOD
    )
    fields = {
        "Account": ExtractedFieldResult(
            field_name="Account", value=12345678, confidence=0.95, is_valid=True
        )
    }
    score = ConfidenceService.calculate_overall_confidence(fields, quality)
    assert score > 0.70
    status = ConfidenceService.determine_document_status(fields, quality, True, score)
    assert status == ExtractionStatus.GOOD
