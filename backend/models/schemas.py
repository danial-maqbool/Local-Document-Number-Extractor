"""
Pydantic schemas and data models for Local Document Number Extractor
"""
from typing import List, Optional, Dict, Any, Union
from enum import Enum
from pydantic import BaseModel, Field
from datetime import datetime

class QualityStatus(str, Enum):
    GOOD = "GOOD"
    REVIEW = "REVIEW"
    LOW_QUALITY = "LOW_QUALITY"
    FAILED = "FAILED"

class ExtractionStatus(str, Enum):
    GOOD = "Good"
    REVIEW = "Review"
    FAILED = "Failed"
    MANUAL = "Manual"

class ExtractionMethod(str, Enum):
    FIXED_REGION = "FIXED_REGION"
    LABEL_PROXIMITY_RIGHT = "LABEL_PROXIMITY_RIGHT"
    LABEL_PROXIMITY_BELOW = "LABEL_PROXIMITY_BELOW"
    LABEL_PROXIMITY_NEAREST = "LABEL_PROXIMITY_NEAREST"
    PATTERN_REGEX = "PATTERN_REGEX"
    GEOMETRY_MATCHING = "GEOMETRY_MATCHING"
    MANUAL_ENTRY = "MANUAL_ENTRY"

class QualityReport(BaseModel):
    blur_score: float
    brightness: float
    contrast: float
    width: int
    height: int
    coverage_score: float = 1.0
    status: QualityStatus
    issues: List[str] = []

class RegionCoords(BaseModel):
    x_min: float = Field(..., ge=0.0, le=1.0, description="Normalized x min (0.0 - 1.0)")
    y_min: float = Field(..., ge=0.0, le=1.0, description="Normalized y min (0.0 - 1.0)")
    x_max: float = Field(..., ge=0.0, le=1.0, description="Normalized x max (0.0 - 1.0)")
    y_max: float = Field(..., ge=0.0, le=1.0, description="Normalized y max (0.0 - 1.0)")

class FieldType(str, Enum):
    INTEGER = "integer"
    DECIMAL = "decimal"
    DATE = "date"
    PHONE = "phone"
    CODE = "code"

class FieldDefinition(BaseModel):
    name: str
    type: FieldType = FieldType.INTEGER
    labels: List[str] = []
    urdu_labels: List[str] = []
    min_digits: Optional[int] = None
    max_digits: Optional[int] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    regex_pattern: Optional[str] = None
    region: Optional[RegionCoords] = None
    required: bool = True
    decimal_allowed: bool = False
    confidence_threshold: float = 0.70

class CrossFieldRule(BaseModel):
    rule_name: str
    description: str
    rule_type: str # e.g. "difference_equals", "sum_equals"
    target_field: str
    operands: List[str]
    tolerance: float = 0.05

class DocumentTemplate(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    fields: List[FieldDefinition]
    cross_field_rules: List[CrossFieldRule] = []

class ExtractionCandidate(BaseModel):
    field_name: str
    raw_value: str
    normalized_value: Union[int, float, str]
    ocr_confidence: float
    field_confidence: float
    bbox: List[int] # [x, y, w, h] in image pixels
    method: ExtractionMethod
    is_selected: bool = False
    rejection_reason: Optional[str] = None
    audit_notes: Optional[str] = None

class ExtractedFieldResult(BaseModel):
    field_name: str
    value: Optional[Union[int, float, str]] = None
    raw_value: Optional[str] = None
    confidence: float = 0.0
    bbox: Optional[List[int]] = None
    method: Optional[ExtractionMethod] = None
    is_valid: bool = False
    is_manual: bool = False
    validation_notes: List[str] = []
    candidates: List[ExtractionCandidate] = []

class DocumentProcessResult(BaseModel):
    document_id: str
    filename: str
    file_hash: str
    original_path: str
    processed_path: Optional[str] = None
    template_id: str
    template_name: str
    quality: QualityReport
    fields: Dict[str, ExtractedFieldResult]
    overall_confidence: float
    status: ExtractionStatus
    cross_field_validation_passed: bool = True
    validation_errors: List[str] = []
    processed_at: datetime = Field(default_factory=datetime.utcnow)

class BatchRunSummary(BaseModel):
    run_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    template_id: str
    total_files: int = 0
    successful: int = 0
    needs_review: int = 0
    failed: int = 0
    average_confidence: float = 0.0
    documents: List[DocumentProcessResult] = []
