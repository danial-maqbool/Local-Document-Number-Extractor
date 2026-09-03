# Local Document Number Extractor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-5C3EE8.svg)](https://opencv.org/)
[![Local Only](https://img.shields.io/badge/Privacy-100%25%20Local-success.svg)](#privacy)

A deterministic, production-grade local application designed to process hundreds of phone-captured document photographs (in English or Urdu), extract user-defined numeric fields, validate them using rule-based and cross-field logic, and export structured results to multi-sheet formatted Excel (`.xlsx`) workbooks.

**100% Local & Offline**: No cloud APIs, no external LLM dependencies, no token billing, zero telemetry.

---

## Why I Built This

Phone-captured bills, receipts, utility invoices, and government forms are plagued by perspective distortion, uneven lighting, shadows, blur, and noisy camera artifacts. While cloud-based LLM or vision APIs exist, they introduce recurring operational costs, variable latency, non-deterministic hallucinations, and—most critically—data privacy and compliance risks for sensitive personal documents.

**Local Document Number Extractor** demonstrates that a specialized, deterministic computer vision and OCR pipeline can solve this problem entirely on-premise. Key capabilities include:
- **Computer Vision Preprocessing**: Document boundary contour detection, 4-point perspective transform, orientation deskew, CLAHE contrast enhancement, and shadow removal.
- **Multilingual & Numeric OCR**: Combined general multilingual OCR (English & Urdu) with constrained numeric OCR whitelist (`0123456789.,-/:`) to maximize character accuracy.
- **Structured Multi-Strategy Extraction**: Field extraction via fixed region coordinates, label proximity search (horizontal and vertical), regex pattern matching, and geometry-relative heuristics.
- **Rule-Based & Cross-Field Validation**: Mathematical consistency checks (e.g. `Units = Current Reading - Previous Reading` or `Subtotal + Tax ≈ Total`) and digit/range validations.
- **Auditable Quality & Confidence Scoring**: Detailed candidate ranking, rejection logging, bounding box tracing, and an interactive manual review queue.
- **Automated Multi-Sheet Excel Output**: Production-ready `.xlsx` workbooks with typed numeric cells, formulas, summaries, and issue breakdowns.

---

## Privacy Statement

> **ALL DOCUMENT PROCESSING OCCURS LOCALLY.**
>
> This application does not connect to any external vision or language model APIs (No OpenAI, No Gemini runtime, No Claude, No Azure OCR, No AWS Textract, No Google Vision). All neural network weights and computer vision algorithms execute entirely on your local CPU or GPU. Document images and extracted values never leave your workstation.

---

## Pipeline Architecture

```text
Input Document Images (.jpg, .png, .tiff, .webp)
               │
               ▼
   [ Image Quality Analysis ]  ──► (Blur, Brightness, Contrast, Resolution)
               │
               ▼
   [ Document Boundary Detection & Perspective Warp ]
               │
               ▼
   [ Deskew & Contrast Enhancement (CLAHE + Shadow Reduction) ]
               │
               ▼
   [ Multilingual & Constrained Numeric OCR ] (EasyOCR / PyTorch)
               │
               ▼
   [ Numeric Candidate Detection & Normalization ]
               │
               ▼
   [ Field Matching Engine ]
    ├── Method A: Fixed Relative Region
    ├── Method B: Label Proximity (Right / Below / Nearest)
    ├── Method C: Regex Pattern Matching
    └── Method D: Geometry & Layout Heuristics
               │
               ▼
   [ Candidate Ranking & Ambiguity Resolution ]
               │
               ▼
   [ Validation Engine ]
    ├── Type & Digit Count Checks
    ├── Numerical Range Checks
    └── Cross-Field Rules (e.g. Math Balance Checks)
               │
               ▼
   [ Confidence Calculation ] (0.00 - 1.00)
               │
      ┌────────┴────────┐
      ▼                 ▼
[ High Confidence ]   [ Low Confidence / Ambiguous / Failed ]
      │                 │
      │                 ▼
      │         [ Manual Review Queue & Debug Inspector ]
      │                 │
      └────────┬────────┘
               ▼
     [ Local SQLite Database ]
               │
               ▼
    [ Multi-Sheet Excel (.xlsx) & CSV Export ]
```

---

## Directory Structure

```text
Local-Document-Number-Extractor/
├── backend/
│   ├── main.py                  # FastAPI Application & Endpoints
│   ├── config.py                # Pipeline & App Configuration
│   ├── models/                  # Pydantic & SQLAlchemy / DB Models
│   └── services/
│       ├── preprocessing.py     # CV2 transforms, deskew, quality analysis
│       ├── ocr_service.py       # Multilingual & Numeric OCR engine
│       ├── extraction_service.py# Multi-strategy field extraction & ranking
│       ├── validation_service.py# Field and cross-field validation rules
│       ├── confidence_service.py# Multi-factor confidence scoring
│       ├── database_service.py  # Local SQLite persistence
│       ├── batch_service.py     # Concurrent batch processing worker
│       └── excel_service.py     # Multi-sheet openpyxl Excel exporter
├── frontend/                    # Local Web Application (Dashboard, Review, Calibration)
├── templates/                   # Predefined and user-custom document templates
├── sample_data/synthetic/       # Synthetic test documents and ground truth
├── tests/                       # Unit and integration test suite
├── docs/                        # In-depth architectural documentation
├── run.py                       # Single-command runner
├── requirements.txt             # Python dependencies
├── LICENSE                      # MIT License
└── README.md
```

---

## Installation & Setup

### Prerequisites
- Python 3.10 or higher
- Git
- (Optional) NVIDIA GPU with CUDA 11.8+ / 12+ for accelerated OCR

### 1. Clone the Repository
```bash
git clone https://github.com/danial-maqbool/Local-Document-Number-Extractor.git
cd Local-Document-Number-Extractor
```

### 2. Set Up a Virtual Environment
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## Running the Application

To launch the local application backend and web interface:
```bash
python run.py
```
Then open your browser at `http://localhost:8000`.

---

## Testing

Run unit and integration tests:
```bash
pytest tests/ -v
```

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
