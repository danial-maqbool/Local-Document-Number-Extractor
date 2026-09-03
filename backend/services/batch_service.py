"""
Local Document Number Extractor - Batch Processing Service
Robust, multi-worker batch pipeline with duplicate detection, fault tolerance, and progress tracking.
"""
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from backend.config import (
    DEFAULT_BATCH_WORKERS, MAX_BATCH_WORKERS, SUPPORTED_EXTENSIONS,
    UPLOADS_DIR, PROCESSED_DIR
)
from backend.models.schemas import (
    DocumentProcessResult, ExtractedFieldResult, QualityReport,
    QualityStatus, ExtractionStatus, DocumentTemplate, BatchRunSummary
)
from backend.services.preprocessing import PreprocessingService
from backend.services.ocr_service import OCRService
from backend.services.extraction_service import ExtractionService
from backend.services.validation_service import ValidationService
from backend.services.confidence_service import ConfidenceService
from backend.services.database_service import DatabaseService

logger = logging.getLogger("extractor.batch")

class BatchService:
    def __init__(self, db_service: Optional[DatabaseService] = None):
        self.db = db_service or DatabaseService()

    def process_single_document(
        self,
        file_path: Path,
        template: DocumentTemplate,
        run_id: Optional[str] = None,
        force_reprocess: bool = False
    ) -> DocumentProcessResult:
        """
        Process a single document image end-to-end:
        1. Duplicate checking via SHA-256
        2. Preprocessing & Quality Analysis (Blur, Deskew, CLAHE, Perspective)
        3. Multilingual & Numeric OCR
        4. Multi-strategy candidate extraction & ranking
        5. Single & Cross-field validations
        6. Confidence evaluation & status assignment
        7. SQLite persistence
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_hash = PreprocessingService.calculate_file_hash(file_path)
        doc_id = f"doc_{file_hash[:16]}"

        # Check duplicate
        if not force_reprocess:
            existing = self.db.check_duplicate_document(file_hash)
            if existing:
                logger.info(f"Reusing existing record for duplicate file {file_path.name} (hash: {file_hash[:8]})")
                full_doc = self.db.get_document(existing["id"])
                if full_doc:
                    if run_id:
                        with self.db.get_connection() as conn:
                            conn.execute("UPDATE documents SET run_id = ? WHERE id = ?", (run_id, existing["id"]))
                            conn.commit()
                    # Construct DocumentProcessResult from DB
                    fields = {}
                    for ext in full_doc.get("extractions", []):
                        val = ext.get("numeric_value") if ext.get("numeric_value") is not None else ext.get("value")
                        fields[ext["field_name"]] = ExtractedFieldResult(
                            field_name=ext["field_name"],
                            value=val,
                            raw_value=ext.get("raw_value"),
                            confidence=ext.get("confidence", 0.0),
                            bbox=ext.get("bbox"),
                            method=ext.get("method"),
                            is_valid=bool(ext.get("is_valid", 0)),
                            is_manual=bool(ext.get("is_manual", 0)),
                            validation_notes=ext.get("validation_notes", [])
                        )
                    return DocumentProcessResult(
                        document_id=full_doc["id"],
                        filename=full_doc["filename"],
                        file_hash=full_doc["file_hash"],
                        original_path=full_doc["original_path"],
                        processed_path=full_doc.get("processed_path"),
                        template_id=full_doc["template_id"],
                        template_name=template.name,
                        quality=QualityReport(
                            blur_score=full_doc.get("blur_score") or 0.0,
                            brightness=full_doc.get("brightness") or 0.0,
                            contrast=full_doc.get("contrast") or 0.0,
                            width=0,
                            height=0,
                            status=QualityStatus(full_doc.get("quality_status") or "GOOD"),
                            issues=full_doc.get("issues", [])
                        ),
                        fields=fields,
                        overall_confidence=full_doc["overall_confidence"],
                        status=ExtractionStatus(full_doc["status"]),
                        cross_field_validation_passed=bool(full_doc.get("cross_field_passed", 1)),
                        validation_errors=full_doc.get("validation_errors", [])
                    )

        # 1. Preprocessing & Quality
        try:
            processed_img, quality, proc_path, meta = PreprocessingService.preprocess_pipeline(
                file_path, output_prefix=f"proc_{doc_id}"
            )
        except Exception as e:
            logger.error(f"Preprocessing failed for {file_path.name}: {e}")
            failed_res = DocumentProcessResult(
                document_id=doc_id,
                filename=file_path.name,
                file_hash=file_hash,
                original_path=str(file_path),
                template_id=template.id,
                template_name=template.name,
                quality=QualityReport(
                    blur_score=0.0, brightness=0.0, contrast=0.0, width=0, height=0,
                    status=QualityStatus.FAILED, issues=[f"Failed to read/preprocess image: {str(e)}"]
                ),
                fields={},
                overall_confidence=0.0,
                status=ExtractionStatus.FAILED,
                cross_field_validation_passed=False,
                validation_errors=[f"Preprocessing exception: {str(e)}"]
            )
            self.db.save_document_result(run_id, failed_res)
            return failed_res

        # If quality is critically low, halt OCR and flag FAILED
        if quality.status == QualityStatus.FAILED:
            failed_res = DocumentProcessResult(
                document_id=doc_id,
                filename=file_path.name,
                file_hash=file_hash,
                original_path=str(file_path),
                processed_path=str(proc_path),
                template_id=template.id,
                template_name=template.name,
                quality=quality,
                fields={},
                overall_confidence=0.0,
                status=ExtractionStatus.FAILED,
                cross_field_validation_passed=False,
                validation_errors=quality.issues
            )
            self.db.save_document_result(run_id, failed_res)
            return failed_res

        # 2. OCR Inference
        ocr_items = OCRService.extract_text_and_boxes(
            processed_img, image_hash=file_hash, force_reprocess=False
        )

        h, w = processed_img.shape[:2]
        extracted_fields: Dict[str, ExtractedFieldResult] = {}
        all_validation_errors: List[str] = []

        # 3. Field Extraction & Ranking
        for field in template.fields:
            cands = ExtractionService.extract_field_candidates(field, ocr_items, img_width=w, img_height=h)

            # If no candidate found from general OCR, attempt direct numeric OCR on expected region
            if not cands and field.region:
                rx = int(field.region.x_min * w)
                ry = int(field.region.y_min * h)
                rw = int((field.region.x_max - field.region.x_min) * w)
                rh = int((field.region.y_max - field.region.y_min) * h)
                roi_items = OCRService.read_numeric_region(processed_img, bbox=[rx, ry, rw, rh])
                for it in roi_items:
                    parsed = ExtractionService.parse_numeric_candidate(it.text, field.type, field.decimal_allowed)
                    if parsed is not None:
                        cands.append(ExtractionCandidate(
                            field_name=field.name,
                            raw_value=it.text,
                            normalized_value=parsed,
                            ocr_confidence=it.confidence,
                            field_confidence=0.88 * it.confidence,
                            bbox=it.bbox,
                            method=ExtractionMethod.FIXED_REGION,
                            audit_notes=f"Targeted numeric OCR on region [{rx},{ry},{rw},{rh}]"
                        ))

            field_result = ExtractionService.rank_candidates(field, cands, img_width=w, img_height=h)

            # 4. Single-field validation
            is_valid, issues = ValidationService.validate_field(field, field_result)
            field_result.is_valid = is_valid
            field_result.validation_notes.extend(issues)
            if issues:
                all_validation_errors.extend(issues)

            extracted_fields[field.name] = field_result

        # 5. Cross-field validation
        cross_passed, cross_errors = ValidationService.validate_cross_fields(template, extracted_fields)
        if cross_errors:
            all_validation_errors.extend(cross_errors)

        # 6. Overall Confidence & Status
        overall_conf = ConfidenceService.calculate_overall_confidence(extracted_fields, quality)
        doc_status = ConfidenceService.determine_document_status(
            extracted_fields, quality, cross_passed, overall_conf
        )

        doc_result = DocumentProcessResult(
            document_id=doc_id,
            filename=file_path.name,
            file_hash=file_hash,
            original_path=str(file_path),
            processed_path=str(proc_path),
            template_id=template.id,
            template_name=template.name,
            quality=quality,
            fields=extracted_fields,
            overall_confidence=overall_conf,
            status=doc_status,
            cross_field_validation_passed=cross_passed,
            validation_errors=all_validation_errors,
            processed_at=datetime.utcnow()
        )

        # 7. Persist to SQLite
        self.db.save_document_result(run_id, doc_result)
        return doc_result

    def process_batch(
        self,
        file_paths: List[Path],
        template: DocumentTemplate,
        run_id: Optional[str] = None,
        max_workers: int = DEFAULT_BATCH_WORKERS,
        progress_callback: Optional[Callable[[int, int, DocumentProcessResult], None]] = None,
        force_reprocess: bool = False
    ) -> BatchRunSummary:
        """
        Execute multi-worker batch processing across document file paths.
        Guarantees fault-isolation: a failing image does not break the batch.
        """
        rid = run_id or f"run_{uuid.uuid4().hex[:8]}"
        summary = BatchRunSummary(
            run_id=rid,
            start_time=datetime.utcnow(),
            template_id=template.id,
            total_files=len(file_paths)
        )
        self.db.save_processing_run(summary)

        workers = max(1, min(max_workers, MAX_BATCH_WORKERS))
        logger.info(f"Starting batch run {rid} ({len(file_paths)} files, {workers} workers)")

        processed_docs: List[DocumentProcessResult] = []
        completed_count = 0

        # Execute concurrent worker pool
        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_file = {
                executor.submit(
                    self.process_single_document,
                    fp, template, rid, force_reprocess
                ): fp for fp in file_paths
            }

            for future in as_completed(future_to_file):
                fp = future_to_file[future]
                completed_count += 1
                try:
                    doc_res = future.result()
                except Exception as exc:
                    logger.error(f"Unhandled error processing {fp.name}: {exc}")
                    doc_res = DocumentProcessResult(
                        document_id=f"doc_err_{uuid.uuid4().hex[:8]}",
                        filename=fp.name,
                        file_hash=f"err_{uuid.uuid4().hex[:8]}",
                        original_path=str(fp),
                        template_id=template.id,
                        template_name=template.name,
                        quality=QualityReport(
                            blur_score=0.0, brightness=0.0, contrast=0.0,
                            width=0, height=0, status=QualityStatus.FAILED,
                            issues=[f"Crash error: {str(exc)}"]
                        ),
                        fields={},
                        overall_confidence=0.0,
                        status=ExtractionStatus.FAILED,
                        cross_field_validation_passed=False,
                        validation_errors=[f"System exception: {str(exc)}"]
                    )
                    self.db.save_document_result(rid, doc_res)

                processed_docs.append(doc_res)

                if doc_res.status == ExtractionStatus.GOOD:
                    summary.successful += 1
                elif doc_res.status == ExtractionStatus.REVIEW:
                    summary.needs_review += 1
                else:
                    summary.failed += 1

                if progress_callback:
                    progress_callback(completed_count, len(file_paths), doc_res)

        summary.end_time = datetime.utcnow()
        summary.documents = processed_docs
        if processed_docs:
            scores = [d.overall_confidence for d in processed_docs if d.status != ExtractionStatus.FAILED]
            summary.average_confidence = round(sum(scores) / len(scores), 4) if scores else 0.0

        self.db.save_processing_run(summary)
        logger.info(
            f"Batch run {rid} finished: {summary.successful} Good, "
            f"{summary.needs_review} Review, {summary.failed} Failed."
        )
        return summary
