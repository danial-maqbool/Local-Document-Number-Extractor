from backend.config import DEVICE, SUPPORTED_EXTENSIONS, TEMPLATES_DIR
from backend.models.schemas import (
    DocumentTemplate, FieldDefinition, FieldType, QualityReport,
    QualityStatus, ExtractedFieldResult, ExtractionMethod
)
import json

def test_config_and_device():
    assert DEVICE in ["cuda", "cpu"]
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".png" in SUPPORTED_EXTENSIONS
    assert TEMPLATES_DIR.exists()

def test_default_templates():
    elec_file = TEMPLATES_DIR / "electricity_bill.json"
    assert elec_file.exists()
    with open(elec_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        template = DocumentTemplate(**data)
        assert template.id == "electricity_bill"
        assert len(template.fields) >= 4
        assert len(template.cross_field_rules) >= 1

def test_schema_instantiation():
    qr = QualityReport(
        blur_score=150.5,
        brightness=120.0,
        contrast=65.0,
        width=1200,
        height=1600,
        status=QualityStatus.GOOD
    )
    assert qr.status == QualityStatus.GOOD
    assert qr.blur_score == 150.5

    result = ExtractedFieldResult(
        field_name="Account Number",
        value=12345678,
        raw_value="12345678",
        confidence=0.98,
        method=ExtractionMethod.FIXED_REGION,
        is_valid=True
    )
    assert result.value == 12345678
    assert result.is_valid is True
