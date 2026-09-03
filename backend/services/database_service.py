"""
Local Document Number Extractor - SQLite Persistence Service
Normalized SQLite database service managing documents, runs, extractions, candidates, and audit logs.
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from datetime import datetime
import uuid

from backend.config import DB_PATH
from backend.models.schemas import (
    DocumentProcessResult, ExtractedFieldResult, ExtractionCandidate,
    BatchRunSummary, QualityReport, QualityStatus, ExtractionStatus, ExtractionMethod
)

logger = logging.getLogger("extractor.database")

class DatabaseService:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_db(self):
        """Initialize normalized database tables and indexes"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Processing runs table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_runs (
                id TEXT PRIMARY KEY,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                template_id TEXT NOT NULL,
                total_files INTEGER DEFAULT 0,
                successful INTEGER DEFAULT 0,
                needs_review INTEGER DEFAULT 0,
                failed INTEGER DEFAULT 0,
                avg_confidence REAL DEFAULT 0.0
            );
            """)

            # Documents table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                run_id TEXT,
                filename TEXT NOT NULL,
                file_hash TEXT NOT NULL,
                original_path TEXT NOT NULL,
                processed_path TEXT,
                template_id TEXT NOT NULL,
                overall_confidence REAL NOT NULL,
                status TEXT NOT NULL,
                blur_score REAL,
                brightness REAL,
                contrast REAL,
                quality_status TEXT,
                issues_json TEXT,
                cross_field_passed INTEGER DEFAULT 1,
                validation_errors_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES processing_runs(id) ON DELETE SET NULL
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_hash ON documents(file_hash);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_status ON documents(status);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_doc_run ON documents(run_id);")

            # Extractions table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS extractions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                raw_value TEXT,
                value TEXT,
                numeric_value REAL,
                confidence REAL NOT NULL,
                bbox_json TEXT,
                method TEXT,
                is_valid INTEGER NOT NULL,
                is_manual INTEGER DEFAULT 0,
                validation_notes_json TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ext_doc ON extractions(document_id);")

            # Extraction candidates table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS extraction_candidates (
                id TEXT PRIMARY KEY,
                extraction_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                raw_value TEXT,
                normalized_value TEXT,
                ocr_confidence REAL NOT NULL,
                field_confidence REAL NOT NULL,
                bbox_json TEXT,
                method TEXT,
                is_selected INTEGER NOT NULL,
                rejection_reason TEXT,
                audit_notes TEXT,
                FOREIGN KEY (extraction_id) REFERENCES extractions(id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_cand_ext ON extraction_candidates(extraction_id);")

            # Manual corrections table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_corrections (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                field_name TEXT NOT NULL,
                previous_value TEXT,
                corrected_value TEXT NOT NULL,
                corrected_by TEXT DEFAULT 'user',
                corrected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE
            );
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_corr_doc ON manual_corrections(document_id);")
            conn.commit()

    def check_duplicate_document(self, file_hash: str) -> Optional[Dict[str, Any]]:
        """Check if image hash was already processed"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, filename, file_hash, overall_confidence, status, created_at
                FROM documents WHERE file_hash = ?
                ORDER BY created_at DESC LIMIT 1;
            """, (file_hash,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def save_processing_run(self, run: BatchRunSummary):
        """Insert or update batch processing run summary"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO processing_runs (
                    id, start_time, end_time, template_id,
                    total_files, successful, needs_review, failed, avg_confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    end_time = excluded.end_time,
                    total_files = excluded.total_files,
                    successful = excluded.successful,
                    needs_review = excluded.needs_review,
                    failed = excluded.failed,
                    avg_confidence = excluded.avg_confidence;
            """, (
                run.run_id,
                run.start_time.isoformat(),
                run.end_time.isoformat() if run.end_time else None,
                run.template_id,
                run.total_files,
                run.successful,
                run.needs_review,
                run.failed,
                run.average_confidence
            ))
            conn.commit()

    def save_document_result(self, run_id: Optional[str], doc: DocumentProcessResult):
        """Save a single document extraction result and all associated field candidates"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Ensure parent run exists if run_id is supplied
            if run_id:
                cursor.execute("""
                    INSERT OR IGNORE INTO processing_runs (id, start_time, template_id)
                    VALUES (?, ?, ?);
                """, (run_id, doc.processed_at.isoformat(), doc.template_id))

            # Insert document with ON CONFLICT UPDATE
            cursor.execute("""
                INSERT INTO documents (
                    id, run_id, filename, file_hash, original_path, processed_path,
                    template_id, overall_confidence, status, blur_score, brightness,
                    contrast, quality_status, issues_json, cross_field_passed,
                    validation_errors_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    run_id = COALESCE(excluded.run_id, documents.run_id),
                    filename = excluded.filename,
                    original_path = excluded.original_path,
                    processed_path = excluded.processed_path,
                    template_id = excluded.template_id,
                    overall_confidence = excluded.overall_confidence,
                    status = excluded.status,
                    blur_score = excluded.blur_score,
                    brightness = excluded.brightness,
                    contrast = excluded.contrast,
                    quality_status = excluded.quality_status,
                    issues_json = excluded.issues_json,
                    cross_field_passed = excluded.cross_field_passed,
                    validation_errors_json = excluded.validation_errors_json;
            """, (
                doc.document_id,
                run_id,
                doc.filename,
                doc.file_hash,
                doc.original_path,
                doc.processed_path,
                doc.template_id,
                doc.overall_confidence,
                doc.status.value,
                doc.quality.blur_score,
                doc.quality.brightness,
                doc.quality.contrast,
                doc.quality.status.value,
                json.dumps(doc.quality.issues),
                1 if doc.cross_field_validation_passed else 0,
                json.dumps(doc.validation_errors),
                doc.processed_at.isoformat()
            ))

            # Remove prior extractions for this document if updating
            cursor.execute("DELETE FROM extractions WHERE document_id = ?", (doc.document_id,))

            # Insert extractions & candidates
            for field_name, field_res in doc.fields.items():
                ext_id = str(uuid.uuid4())
                numeric_val = None
                if isinstance(field_res.value, (int, float)):
                    numeric_val = float(field_res.value)

                cursor.execute("""
                    INSERT INTO extractions (
                        id, document_id, field_name, raw_value, value, numeric_value,
                        confidence, bbox_json, method, is_valid, is_manual, validation_notes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """, (
                    ext_id,
                    doc.document_id,
                    field_name,
                    field_res.raw_value,
                    str(field_res.value) if field_res.value is not None else None,
                    numeric_val,
                    field_res.confidence,
                    json.dumps(field_res.bbox) if field_res.bbox else None,
                    field_res.method.value if field_res.method else None,
                    1 if field_res.is_valid else 0,
                    1 if field_res.is_manual else 0,
                    json.dumps(field_res.validation_notes)
                ))

                # Insert candidates for debug inspector
                for cand in field_res.candidates:
                    cand_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO extraction_candidates (
                            id, extraction_id, field_name, raw_value, normalized_value,
                            ocr_confidence, field_confidence, bbox_json, method,
                            is_selected, rejection_reason, audit_notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        cand_id,
                        ext_id,
                        cand.field_name,
                        cand.raw_value,
                        str(cand.normalized_value),
                        cand.ocr_confidence,
                        cand.field_confidence,
                        json.dumps(cand.bbox),
                        cand.method.value if cand.method else None,
                        1 if cand.is_selected else 0,
                        cand.rejection_reason,
                        cand.audit_notes
                    ))

            conn.commit()

    def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full document detail including extractions, candidates, and manual edits"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            doc_row = cursor.fetchone()
            if not doc_row:
                return None

            doc_dict = dict(doc_row)
            doc_dict["issues"] = json.loads(doc_dict.get("issues_json") or "[]")
            doc_dict["validation_errors"] = json.loads(doc_dict.get("validation_errors_json") or "[]")

            # Fetch extractions
            cursor.execute("SELECT * FROM extractions WHERE document_id = ?", (doc_id,))
            extractions = []
            for ext in cursor.fetchall():
                e_dict = dict(ext)
                e_dict["bbox"] = json.loads(e_dict.get("bbox_json") or "null")
                e_dict["validation_notes"] = json.loads(e_dict.get("validation_notes_json") or "[]")

                # Fetch candidates
                cursor.execute("SELECT * FROM extraction_candidates WHERE extraction_id = ?", (e_dict["id"],))
                cands = []
                for cand in cursor.fetchall():
                    c_dict = dict(cand)
                    c_dict["bbox"] = json.loads(c_dict.get("bbox_json") or "[]")
                    cands.append(c_dict)
                e_dict["candidates"] = cands
                extractions.append(e_dict)

            doc_dict["extractions"] = extractions

            # Fetch manual corrections
            cursor.execute("SELECT * FROM manual_corrections WHERE document_id = ? ORDER BY corrected_at DESC", (doc_id,))
            doc_dict["manual_corrections"] = [dict(r) for r in cursor.fetchall()]

            return doc_dict

    def list_documents(
        self,
        run_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """List documents with optional filtering"""
        query = "SELECT * FROM documents WHERE 1=1"
        params: List[Any] = []

        if run_id:
            query += " AND run_id = ?"
            params.append(run_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if search:
            query += " AND filename LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY created_at DESC;"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, tuple(params))
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                cursor.execute("SELECT field_name, value, numeric_value, confidence, is_valid, is_manual FROM extractions WHERE document_id = ?", (d["id"],))
                fields = {}
                for ext in cursor.fetchall():
                    fields[ext["field_name"]] = {
                        "value": ext["numeric_value"] if ext["numeric_value"] is not None else ext["value"],
                        "confidence": ext["confidence"],
                        "is_valid": bool(ext["is_valid"]),
                        "is_manual": bool(ext["is_manual"])
                    }
                d["fields"] = fields
                results.append(d)
            return results

    def save_manual_correction(
        self,
        doc_id: str,
        field_name: str,
        new_value: Union[int, float, str],
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Record a manual correction for a document field:
        1. Updates extractions value and sets is_manual=1, is_valid=1
        2. Logs audit trail in manual_corrections table
        3. Recalculates document status if needed
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, value, numeric_value FROM extractions WHERE document_id = ? AND field_name = ?", (doc_id, field_name))
            ext_row = cursor.fetchone()
            prev_val = ext_row["value"] if ext_row else None

            numeric_val = None
            try:
                numeric_val = float(new_value)
            except (ValueError, TypeError):
                pass

            if ext_row:
                cursor.execute("""
                    UPDATE extractions
                    SET value = ?, numeric_value = ?, is_manual = 1, is_valid = 1, confidence = 1.0, method = 'MANUAL_ENTRY'
                    WHERE id = ?;
                """, (str(new_value), numeric_val, ext_row["id"]))
            else:
                ext_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO extractions (
                        id, document_id, field_name, raw_value, value, numeric_value,
                        confidence, bbox_json, method, is_valid, is_manual, validation_notes_json
                    ) VALUES (?, ?, ?, ?, ?, ?, 1.0, null, 'MANUAL_ENTRY', 1, 1, '["Manually entered"]');
                """, (ext_id, doc_id, field_name, str(new_value), str(new_value), numeric_val))

            # Audit record
            corr_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO manual_corrections (
                    id, document_id, field_name, previous_value, corrected_value, notes
                ) VALUES (?, ?, ?, ?, ?, ?);
            """, (corr_id, doc_id, field_name, str(prev_val), str(new_value), notes))

            # Re-evaluate document status: if all fields valid now, set status to Good
            cursor.execute("SELECT COUNT(*) as invalid_count FROM extractions WHERE document_id = ? AND is_valid = 0", (doc_id,))
            inv_count = cursor.fetchone()["invalid_count"]
            new_status = "Good" if inv_count == 0 else "Review"
            cursor.execute("UPDATE documents SET status = ? WHERE id = ?", (new_status, doc_id))

            conn.commit()
            return {"status": "success", "field": field_name, "new_value": new_value, "doc_status": new_status}

    def list_runs(self) -> List[Dict[str, Any]]:
        """List all processing runs history"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM processing_runs ORDER BY start_time DESC;")
            return [dict(r) for r in cursor.fetchall()]
