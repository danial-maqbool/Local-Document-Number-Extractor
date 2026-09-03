# Architecture Documentation: Local Document Number Extractor

This document describes the architectural design and stage-by-stage data flow of the **Local Document Number Extractor** system.

```
                  ┌───────────────────────────────┐
                  │   Image Input (.jpg, .png)    │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │    Image Quality Analysis     │
                  │ (Blur, Brightness, Contrast)  │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │  Document Contour Detection   │
                  │   & Perspective Rectification │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │      Image Enhancement        │
                  │   (Deskew, CLAHE, Denoise)    │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │       Dual-Path OCR           │
                  │  Text (Urdu/EN) + Numeric Box │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │  Numeric Candidate Detection  │
                  │     & Normalization (O->0)    │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │   Template & Label Matching   │
                  │  (Fixed, Proximity, Patterns) │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │  Candidate Ranking & Scorer   │
                  │    (Distance, Range, BBox)    │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │  Field & Cross-Field Rules    │
                  │  (Math Balance & Digit Checks)│
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │     Confidence Evaluation     │
                  └──────────────┬────────────────┘
                                 │
                    ┌────────────┴───────────┐
                    │                        │
         [Score >= Threshold]      [Low Conf / Ambiguous]
                    │                        │
                    │                        ▼
                    │             ┌─────────────────────┐
                    │             │ Manual Review Queue │
                    │             └──────────┬──────────┘
                    │                        │
                    └────────────┬───────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │        SQLite Storage         │
                  └──────────────┬────────────────┘
                                 │
                                 ▼
                  ┌───────────────────────────────┐
                  │  Multi-Sheet Excel (.xlsx)    │
                  │     & CSV Data Exporter       │
                  └───────────────────────────────┘
```

---

## 1. Image Quality Analysis
Before expensive OCR runs, the image is evaluated:
- **Blur Detection**: Variance of Laplacian metric. Sharp images have high variance, blurry images have low variance.
- **Brightness & Contrast**: Standard deviation of pixel intensities and mean grayscale luminosity.
- **Resolution**: Assesses minimum dimensions for reliable text recognition.
Images below critical thresholds are flagged as `REVIEW`, `LOW_QUALITY`, or `FAILED`.

## 2. Document Detection & Perspective Correction
Phone photos frequently exhibit perspective tilting.
- Preprocessing applies Gaussian blur and Otsu / adaptive edge detection.
- Finds largest quadrilateral contour covering a significant portion of the image.
- Computes standard 4-point perspective transform to rectify the document into a flat rectangular plane.

## 3. Image Enhancement & Deskew
- **Deskew**: Computes dominant orientation angle using Hough lines or minimum area bounding boxes and rotates image back to 0 degrees.
- **Shadow Removal & CLAHE**: Contrast Limited Adaptive Histogram Equalization compensates for phone shadows and non-uniform lighting.
- **Bilateral Filtering**: Reduces noise while strictly preserving sharp text edges.

## 4. Multilingual & Constrained Numeric OCR
- **Multilingual General Engine**: EasyOCR configured with English (`en`) and Urdu (`ur`) for detecting field labels, headers, and section identifiers.
- **Constrained Numeric Engine**: Region-specific recognition restricted to `0123456789.,-/:` to prevent common alphanumeric character confusion.
- Loaded once in memory during service startup and shared across batch runs.

## 5. Numeric Candidate Detection & Normalization
- Extracts raw bounding boxes and candidate text fragments.
- Normalizes common OCR substitutions in numeric context:
  `O -> 0`, `I -> 1`, `l -> 1`, `S -> 5`, `B -> 8`.
- Records raw vs normalized values for complete auditability.

## 6. Multi-Strategy Field Matching
Supports 5 deterministic strategies in prioritized sequence:
1. **Method A (Fixed Region)**: Normalized relative coordinates `(x_min, y_min, x_max, y_max)` as configured in document templates.
2. **Method B (Label Proximity)**: Locates field labels (English and Urdu) and searches right, below, or within radial distance.
3. **Method C (Pattern Matching)**: Evaluates regex specifications (e.g. `\b\d{10,14}\b`).
4. **Method D (Geometry Matching)**: Enforces relational positions (e.g. `Current Reading` positioned below or right of `Previous Reading`).
5. **Method E (Candidate Ranking)**: Ranks ambiguous candidates by compound metric factoring distance, OCR confidence, digit count match, and value range.

## 7. Validation Engine & Cross-Field Validation
- **Single-Field Validation**: Evaluates numeric types, allowed decimals, digit lengths, and ranges.
- **Cross-Field Validation**: Evaluates mathematical relationships across fields (e.g. `Units = Current Reading - Previous Reading` or `Subtotal + Tax = Grand Total`) within configurable tolerances. Discrepancies trigger audit flags.

## 8. Confidence Calculation & Ambiguity Flagging
- Evaluates OCR confidence, label proximity score, template adherence, and validation status.
- When two candidates differ by less than `AMBIGUITY_DELTA_THRESHOLD`, marked as `AMBIGUOUS`.

## 9. Manual Review Queue
- Low-confidence, ambiguous, or rule-failing records enter the review queue.
- Shows original image, rectified image, bounding boxes, candidate list, and rejection reasons.
- Corrections persist with audit mark `MANUAL`.

## 10. Persistence & Excel Export
- Normalized SQLite database stores files, runs, extractions, candidates, and manual edits.
- Generates multi-sheet `.xlsx` files using `openpyxl`:
  - `Extracted Data`
  - `Needs Review`
  - `Failed`
  - `Processing Summary`
- Numeric values are explicitly saved as numeric Excel cells with auto-filter and formatting.
