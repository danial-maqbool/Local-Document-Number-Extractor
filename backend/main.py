"""
Local Document Number Extractor - FastAPI Backend
100% Local, Fully Deterministic
"""
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from typing import List, Optional
import os
import json
import logging
from pathlib import Path

from backend.config import (
    DEVICE, DEFAULT_OCR_LANGUAGES, DATA_DIR, UPLOADS_DIR,
    PROCESSED_DIR, EXPORTS_DIR, TEMPLATES_DIR, BASE_DIR
)
from backend.models.schemas import DocumentTemplate, BatchRunSummary

# Configure local logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("extractor")

app = FastAPI(
    title="Local Document Number Extractor",
    description="High-precision multilingual local document numeric field extraction",
    version="1.0.0"
)

# Allow local CORS for local web interface
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve processed and export files statically
app.mount("/static/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/static/processed", StaticFiles(directory=str(PROCESSED_DIR)), name="processed")
app.mount("/static/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")

# Mount frontend if build directory exists
FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/app", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")

@app.get("/api/health")
async def health_check():
    """Health check endpoint indicating runtime device and status"""
    return {
        "status": "healthy",
        "device": DEVICE,
        "supported_languages": DEFAULT_OCR_LANGUAGES,
        "local_only": True,
        "external_api_calls": False
    }

@app.get("/api/templates", response_model=List[DocumentTemplate])
async def list_templates():
    """List all available document templates"""
    templates = []
    for t_file in TEMPLATES_DIR.glob("*.json"):
        try:
            with open(t_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                templates.append(DocumentTemplate(**data))
        except Exception as e:
            logger.error(f"Error loading template {t_file}: {e}")
    return templates

@app.get("/api/templates/{template_id}", response_model=DocumentTemplate)
async def get_template(template_id: str):
    """Get a single document template by ID"""
    t_file = TEMPLATES_DIR / f"{template_id}.json"
    if not t_file.exists():
        raise HTTPException(status_code=404, detail="Template not found")
    with open(t_file, "r", encoding="utf-8") as f:
        data = json.load(f)
        return DocumentTemplate(**data)

@app.post("/api/templates", response_model=DocumentTemplate)
async def save_template(template: DocumentTemplate):
    """Save or update a document template"""
    t_file = TEMPLATES_DIR / f"{template.id}.json"
    with open(t_file, "w", encoding="utf-8") as f:
        f.write(template.model_dump_json(indent=2))
    return template

@app.get("/")
async def root():
    """Root redirect / landing info"""
    return {
        "name": "Local Document Number Extractor API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health"
    }
