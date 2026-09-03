"""
Local Document Number Extractor - FastAPI Application
100% Local, Fully Deterministic Backend API
"""
import os
import shutil
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel

from backend.config import (
    DEVICE, DEFAULT_OCR_LANGUAGES, DATA_DIR, UPLOADS_DIR,
    PROCESSED_DIR, EXPORTS_DIR, TEMPLATES_DIR, BASE_DIR, LOGS_DIR
)
from backend.models.schemas import (
    DocumentTemplate, BatchRunSummary, DocumentProcessResult,
    ExtractionStatus
)
from backend.services.database_service import DatabaseService
from backend.services.batch_service import BatchService
from backend.services.excel_service import ExcelService
from backend.services.preprocessing import PreprocessingService

# Setup logger
logger = logging.getLogger("extractor.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(
    title="Local Document Number Extractor",
    description="High-precision multilingual document numeric field extraction running 100% locally.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = DatabaseService()
batch_service = BatchService(db_service=db)

# Static file mounts
app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static/processed", StaticFiles(directory=str(PROCESSED_DIR)), name="processed")
app.mount("/static/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")
app.mount("/static/synthetic", StaticFiles(directory=str(BASE_DIR / "sample_data" / "synthetic")), name="synthetic")

# Mount frontend files
FRONTEND_DIR = BASE_DIR / "frontend"

@app.get("/style.css")
async def get_root_style():
    css_file = FRONTEND_DIR / "style.css"
    if css_file.exists():
        return FileResponse(str(css_file), media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")

@app.get("/app.js")
async def get_root_app_js():
    js_file = FRONTEND_DIR / "app.js"
    if js_file.exists():
        return FileResponse(str(js_file), media_type="application/javascript")
    raise HTTPException(status_code=404, detail="app.js not found")

@app.get("/ui")
async def get_ui():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file), media_type="text/html")
    raise HTTPException(status_code=404, detail="index.html not found")

if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend_ui")

@app.get("/api/health")
async def health():
    return {
        "status": "online",
        "device": DEVICE,
        "supported_languages": DEFAULT_OCR_LANGUAGES,
        "local_only": True,
        "runtime_api_tokens": False
    }

# -------------------------------------------------------------
# Template Endpoints
# -------------------------------------------------------------
@app.get("/api/templates", response_model=List[DocumentTemplate])
async def list_templates():
    templates = []
    for t_file in TEMPLATES_DIR.glob("*.json"):
        try:
            with open(t_file, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
                templates.append(DocumentTemplate(**data))
        except Exception as e:
            logger.error(f"Error loading template {t_file}: {e}")
    return templates

@app.get("/api/templates/{template_id}", response_model=DocumentTemplate)
async def get_template(template_id: str):
    t_file = TEMPLATES_DIR / f"{template_id}.json"
    if not t_file.exists():
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")
    with open(t_file, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
        return DocumentTemplate(**data)

@app.post("/api/templates", response_model=DocumentTemplate)
async def save_template(template: DocumentTemplate):
    t_file = TEMPLATES_DIR / f"{template.id}.json"
    with open(t_file, "w", encoding="utf-8") as f:
        f.write(template.model_dump_json(indent=2))
    return template

@app.delete("/api/templates/{template_id}")
async def delete_template(template_id: str):
    t_file = TEMPLATES_DIR / f"{template_id}.json"
    if t_file.exists():
        t_file.unlink()
        return {"status": "deleted", "template_id": template_id}
    raise HTTPException(status_code=404, detail="Template not found")

# -------------------------------------------------------------
# Document & Extraction Endpoints
# -------------------------------------------------------------
@app.get("/api/documents")
async def get_documents(
    run_id: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None
):
    return db.list_documents(run_id=run_id, status=status, search=search)

@app.get("/api/documents/{doc_id}")
async def get_document_details(doc_id: str):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc

@app.get("/api/documents/{doc_id}/image")
async def get_document_image(doc_id: str):
    doc = db.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    filename = doc.get("filename", "")
    paths_to_try = [
        Path(doc["processed_path"]) if doc.get("processed_path") else None,
        Path(doc["original_path"]) if doc.get("original_path") else None,
        BASE_DIR / doc.get("original_path", ""),
        UPLOADS_DIR / filename,
        BASE_DIR / "sample_data" / "synthetic" / filename,
        BASE_DIR / "real_test_docs" / filename
    ]
    for p in paths_to_try:
        if p and p.is_file():
            suffix = p.suffix.lower()
            media_type = "image/jpeg"
            if suffix == ".png":
                media_type = "image/png"
            elif suffix == ".webp":
                media_type = "image/webp"
            elif suffix in (".tif", ".tiff"):
                media_type = "image/tiff"
            return FileResponse(str(p), media_type=media_type)
    raise HTTPException(status_code=404, detail="Document image file not found")

class ManualCorrectionRequest(BaseModel):
    field_name: str
    corrected_value: Any
    notes: Optional[str] = ""

@app.post("/api/documents/{doc_id}/correct")
async def correct_field(doc_id: str, req: ManualCorrectionRequest):
    res = db.save_manual_correction(
        doc_id=doc_id,
        field_name=req.field_name,
        new_value=req.corrected_value,
        notes=req.notes or ""
    )
    return res

# -------------------------------------------------------------
# Batch Processing Endpoints
# -------------------------------------------------------------
@app.post("/api/batch/process")
async def process_batch_files(
    template_id: str = Form(...),
    workers: int = Form(2),
    force_reprocess: bool = Form(False),
    files: List[UploadFile] = File(...)
):
    t_file = TEMPLATES_DIR / f"{template_id}.json"
    if not t_file.exists():
        raise HTTPException(status_code=404, detail=f"Template {template_id} not found")

    with open(t_file, "r", encoding="utf-8-sig") as f:
        template = DocumentTemplate(**json.load(f))

    saved_paths: List[Path] = []
    for upload in files:
        target_path = UPLOADS_DIR / upload.filename
        with open(target_path, "wb") as buffer:
            shutil.copyfileobj(upload.file, buffer)
        saved_paths.append(target_path)

    summary = batch_service.process_batch(
        file_paths=saved_paths,
        template=template,
        max_workers=workers,
        force_reprocess=force_reprocess
    )

    return {
        "run_id": summary.run_id,
        "total_files": summary.total_files,
        "successful": summary.successful,
        "needs_review": summary.needs_review,
        "failed": summary.failed,
        "average_confidence": summary.average_confidence
    }

@app.post("/api/batch/process_synthetic")
async def process_synthetic_benchmark(
    template_id: str = Form("electricity_bill"),
    workers: int = Form(2)
):
    """Trigger processing on generated synthetic dataset"""
    t_file = TEMPLATES_DIR / f"{template_id}.json"
    if not t_file.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    with open(t_file, "r", encoding="utf-8-sig") as f:
        template = DocumentTemplate(**json.load(f))

    synthetic_dir = BASE_DIR / "sample_data" / "synthetic"
    if not synthetic_dir.exists():
        raise HTTPException(status_code=400, detail="Synthetic data not generated yet")

    prefix = "bill_doc_" if template_id == "electricity_bill" else "invoice_doc_"
    files = sorted(list(synthetic_dir.glob(f"{prefix}*.jpg")))

    summary = batch_service.process_batch(
        file_paths=files,
        template=template,
        max_workers=workers,
        force_reprocess=True
    )
    return summary

@app.get("/api/runs")
async def list_runs():
    return db.list_runs()

# -------------------------------------------------------------
# Export Endpoints
# -------------------------------------------------------------
@app.get("/api/export/excel/{template_id}")
async def export_excel(template_id: str, run_id: Optional[str] = None):
    t_file = TEMPLATES_DIR / f"{template_id}.json"
    if not t_file.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    with open(t_file, "r", encoding="utf-8-sig") as f:
        template = DocumentTemplate(**json.load(f))

    docs = db.list_documents(run_id=run_id)
    # Reconstruct DocumentProcessResults
    results: List[DocumentProcessResult] = []
    for d in docs:
        full_d = db.get_document(d["id"])
        if full_d:
            fields = {}
            for ext in full_d.get("extractions", []):
                val = ext.get("numeric_value") if ext.get("numeric_value") is not None else ext.get("value")
                fields[ext["field_name"]] = DocumentProcessResult.model_construct(
                    value=val
                )
            results.append(DocumentProcessResult(
                document_id=full_d["id"],
                filename=full_d["filename"],
                file_hash=full_d["file_hash"],
                original_path=full_d["original_path"],
                processed_path=full_d.get("processed_path"),
                template_id=template_id,
                template_name=template.name,
                quality=DocumentProcessResult.model_construct(
                    blur_score=full_d.get("blur_score", 0.0),
                    brightness=full_d.get("brightness", 0.0),
                    contrast=full_d.get("contrast", 0.0),
                    status=full_d.get("quality_status", "GOOD"),
                    issues=full_d.get("issues", [])
                ),
                fields=fields,
                overall_confidence=full_d["overall_confidence"],
                status=ExtractionStatus(full_d["status"]),
                cross_field_validation_passed=bool(full_d.get("cross_field_passed", 1)),
                validation_errors=full_d.get("validation_errors", [])
            ))

    file_path = ExcelService.export_results_to_excel(results, template)
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

@app.get("/api/export/csv/{template_id}")
async def export_csv(template_id: str, run_id: Optional[str] = None):
    t_file = TEMPLATES_DIR / f"{template_id}.json"
    if not t_file.exists():
        raise HTTPException(status_code=404, detail="Template not found")

    with open(t_file, "r", encoding="utf-8-sig") as f:
        template = DocumentTemplate(**json.load(f))

    docs = db.list_documents(run_id=run_id)
    results: List[DocumentProcessResult] = []
    for d in docs:
        full_d = db.get_document(d["id"])
        if full_d:
            fields = {}
            for ext in full_d.get("extractions", []):
                val = ext.get("numeric_value") if ext.get("numeric_value") is not None else ext.get("value")
                fields[ext["field_name"]] = DocumentProcessResult.model_construct(
                    value=val
                )
            results.append(DocumentProcessResult(
                document_id=full_d["id"],
                filename=full_d["filename"],
                file_hash=full_d["file_hash"],
                original_path=full_d["original_path"],
                processed_path=full_d.get("processed_path"),
                template_id=template_id,
                template_name=template.name,
                quality=DocumentProcessResult.model_construct(
                    blur_score=full_d.get("blur_score", 0.0),
                    brightness=full_d.get("brightness", 0.0),
                    contrast=full_d.get("contrast", 0.0),
                    status=full_d.get("quality_status", "GOOD"),
                    issues=full_d.get("issues", [])
                ),
                fields=fields,
                overall_confidence=full_d["overall_confidence"],
                status=ExtractionStatus(full_d["status"]),
                cross_field_validation_passed=bool(full_d.get("cross_field_passed", 1)),
                validation_errors=full_d.get("validation_errors", [])
            ))

    file_path = ExcelService.export_results_to_csv(results, template)
    return FileResponse(
        path=str(file_path),
        filename=file_path.name,
        media_type="text/csv"
    )

@app.get("/api/benchmark/report")
async def get_benchmark_report():
    report_file = BASE_DIR / "sample_data" / "synthetic" / "evaluation_report.json"
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Benchmark report not yet computed")
    with open(report_file, "r", encoding="utf-8") as f:
        return json.load(f)

# Root landing redirect
@app.get("/")
async def root():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return {
        "name": "Local Document Number Extractor",
        "docs": "/docs",
        "health": "/api/health"
    }
