import pytest
from pathlib import Path
from datetime import datetime
from backend.services.database_service import DatabaseService
from backend.models.schemas import (
    DocumentProcessResult, ExtractedFieldResult, ExtractionCandidate,
    QualityReport, QualityStatus, ExtractionStatus, ExtractionMethod, BatchRunSummary
)

@pytest.fixture
def temp_db(tmp_path):
    db_file = tmp_path / "test_extract.db"
    return DatabaseService(db_path=db_file)

def test_database_init(temp_db):
    with temp_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [r[0] for r in cursor.fetchall()]
        assert "documents" in tables
        assert "extractions" in tables
        assert "extraction_candidates" in tables
        assert "manual_corrections" in tables
        assert "processing_runs" in tables

def test_save_and_retrieve_document(temp_db):
    qr = QualityReport(
        blur_score=140.0, brightness=120.0, contrast=60.0,
        width=800, height=1000, status=QualityStatus.GOOD
    )
    cand = ExtractionCandidate(
        field_name="Account Number",
        raw_value="382947291",
        normalized_value=382947291,
        ocr_confidence=0.98,
        field_confidence=0.96,
        bbox=[100, 150, 120, 30],
        method=ExtractionMethod.LABEL_PROXIMITY_RIGHT,
        is_selected=True
    )
    field_res = ExtractedFieldResult(
        field_name="Account Number",
        value=382947291,
        raw_value="382947291",
        confidence=0.96,
        bbox=[100, 150, 120, 30],
        method=ExtractionMethod.LABEL_PROXIMITY_RIGHT,
        is_valid=True,
        candidates=[cand]
    )
    doc_res = DocumentProcessResult(
        document_id="doc_123",
        filename="bill_01.jpg",
        file_hash="abcd1234efgh5678",
        original_path="/path/bill_01.jpg",
        template_id="electricity_bill",
        template_name="Electricity Bill",
        quality=qr,
        fields={"Account Number": field_res},
        overall_confidence=0.96,
        status=ExtractionStatus.GOOD
    )

    temp_db.save_document_result("run_1", doc_res)

    retrieved = temp_db.get_document("doc_123")
    assert retrieved is not None
    assert retrieved["filename"] == "bill_01.jpg"
    assert retrieved["file_hash"] == "abcd1234efgh5678"
    assert len(retrieved["extractions"]) == 1
    assert retrieved["extractions"][0]["field_name"] == "Account Number"
    assert retrieved["extractions"][0]["numeric_value"] == 382947291
    assert len(retrieved["extractions"][0]["candidates"]) == 1

def test_duplicate_detection(temp_db):
    dup = temp_db.check_duplicate_document("abcd1234efgh5678")
    assert dup is None

def test_manual_correction_and_audit(temp_db):
    qr = QualityReport(blur_score=100.0, brightness=100.0, contrast=50.0, width=500, height=500, status=QualityStatus.GOOD)
    field_res = ExtractedFieldResult(
        field_name="Units", value=150, raw_value="15O", confidence=0.60, is_valid=False
    )
    doc_res = DocumentProcessResult(
        document_id="doc_rev", filename="rev.jpg", file_hash="hash_rev",
        original_path="/p/rev.jpg", template_id="electricity_bill", template_name="Electricity Bill",
        quality=qr, fields={"Units": field_res}, overall_confidence=0.60, status=ExtractionStatus.REVIEW
    )
    temp_db.save_document_result("run_rev", doc_res)

    # Make manual correction
    corr_res = temp_db.save_manual_correction("doc_rev", "Units", 180, notes="User corrected OCR mistake")
    assert corr_res["status"] == "success"
    assert corr_res["doc_status"] == "Good"

    # Verify audit log
    doc = temp_db.get_document("doc_rev")
    assert doc["status"] == "Good"
    assert len(doc["manual_corrections"]) == 1
    assert doc["manual_corrections"][0]["previous_value"] == "150"
    assert doc["manual_corrections"][0]["corrected_value"] == "180"
