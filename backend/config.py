"""
Local Document Number Extractor - Global Configuration
Deterministic, 100% Local Processing Configuration
"""
from pathlib import Path
import os
import torch

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
PROCESSED_DIR = DATA_DIR / "processed"
EXPORTS_DIR = DATA_DIR / "exports"
CACHE_DIR = DATA_DIR / "cache"
DB_PATH = DATA_DIR / "extractor.db"
TEMPLATES_DIR = BASE_DIR / "templates"
LOGS_DIR = BASE_DIR / "logs"

# Ensure runtime directories exist
for p in [DATA_DIR, UPLOADS_DIR, PROCESSED_DIR, EXPORTS_DIR, CACHE_DIR, TEMPLATES_DIR, LOGS_DIR]:
    p.mkdir(parents=True, exist_ok=True)

# Supported image formats
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff"}

# Device Detection: CUDA or CPU
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# Image Quality Thresholds
QUALITY_BLUR_THRESHOLD_FAILED = 30.0    # Variance of Laplacian < 30 -> FAILED
QUALITY_BLUR_THRESHOLD_REVIEW = 60.0    # Variance of Laplacian < 60 -> REVIEW
QUALITY_MIN_WIDTH = 300
QUALITY_MIN_HEIGHT = 300
QUALITY_BRIGHTNESS_MIN = 35             # 0 - 255
QUALITY_BRIGHTNESS_MAX = 230
QUALITY_CONTRAST_MIN = 25

# OCR Default Settings
DEFAULT_OCR_LANGUAGES = ["en", "ur"]
NUMERIC_CHAR_WHITELIST = "0123456789.,-/: "
DEFAULT_CONFIDENCE_THRESHOLD = 0.70
AMBIGUITY_DELTA_THRESHOLD = 0.08        # If top 2 candidates have confidence delta < 0.08 -> flag ambiguous

# Batch Processing
DEFAULT_BATCH_WORKERS = 2
MAX_BATCH_WORKERS = 4
