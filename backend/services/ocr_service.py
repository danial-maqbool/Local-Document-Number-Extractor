"""
Local Document Number Extractor - Multilingual & Numeric OCR Service
Deterministic, 100% Local Inference Engine with Singleton Architecture and Model Caching.
"""
import os
import json
import re
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
import cv2
import easyocr

from backend.config import (
    DEVICE, DEFAULT_OCR_LANGUAGES, NUMERIC_CHAR_WHITELIST,
    CACHE_DIR
)

logger = logging.getLogger("extractor.ocr")

class OCRItem:
    def __init__(
        self,
        text: str,
        confidence: float,
        bbox: List[int], # [x, y, w, h]
        norm_bbox: List[float], # [x_min, y_min, x_max, y_max]
        is_numeric: bool = False
    ):
        self.text = text
        self.confidence = round(float(confidence), 4)
        self.bbox = bbox
        self.norm_bbox = [round(c, 4) for c in norm_bbox]
        self.is_numeric = is_numeric

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "confidence": self.confidence,
            "bbox": self.bbox,
            "norm_bbox": self.norm_bbox,
            "is_numeric": self.is_numeric
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OCRItem":
        return cls(
            text=data["text"],
            confidence=data["confidence"],
            bbox=data["bbox"],
            norm_bbox=data["norm_bbox"],
            is_numeric=data.get("is_numeric", False)
        )

class OCRService:
    _instance: Optional["OCRService"] = None
    _reader: Optional[easyocr.Reader] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCRService, cls).__new__(cls)
        return cls._instance

    @classmethod
    def initialize(cls, gpu: Optional[bool] = None, languages: Optional[List[str]] = None) -> None:
        """
        Load EasyOCR models once in memory.
        Reuses cached weights across all document processing tasks.
        """
        if cls._reader is not None and cls._initialized:
            return

        use_gpu = gpu if gpu is not None else (DEVICE == "cuda")
        langs = languages or DEFAULT_OCR_LANGUAGES
        
        logger.info(f"Initializing local EasyOCR Reader (languages={langs}, gpu={use_gpu})...")
        try:
            cls._reader = easyocr.Reader(langs, gpu=use_gpu)
            cls._initialized = True
            logger.info(f"EasyOCR Reader successfully initialized on device: {cls._reader.device}")
        except Exception as e:
            logger.warning(f"Failed to initialize EasyOCR with GPU={use_gpu}, falling back to CPU: {e}")
            cls._reader = easyocr.Reader(langs, gpu=False)
            cls._initialized = True
            logger.info("EasyOCR Reader successfully initialized on CPU.")

    @classmethod
    def get_reader(cls) -> easyocr.Reader:
        if cls._reader is None or not cls._initialized:
            cls.initialize()
        return cls._reader

    @staticmethod
    def normalize_numeric_string(raw_str: str) -> Tuple[str, List[str]]:
        """
        Carefully normalize common OCR substitutions inside numeric context:
        O/o -> 0, I/l/|/! -> 1, Z/z -> 2, S/s -> 5, B -> 8
        Returns: (normalized_str, list_of_transformations)
        """
        replacements = {
            'O': '0', 'o': '0',
            'I': '1', 'l': '1', '|': '1', '!': '1',
            'Z': '2', 'z': '2',
            'S': '5', 's': '5',
            'B': '8'
        }
        modifications = []
        chars = list(raw_str)
        for idx, char in enumerate(chars):
            if char in replacements:
                orig = char
                rep = replacements[char]
                chars[idx] = rep
                modifications.append(f"Position {idx}: '{orig}' -> '{rep}'")
        
        normalized = "".join(chars)
        return normalized, modifications

    @classmethod
    def get_cache_key(cls, image_hash: str, options: Dict[str, Any]) -> str:
        data = f"{image_hash}_{json.dumps(options, sort_keys=True)}"
        return hashlib.sha256(data.encode("utf-8")).hexdigest()

    @classmethod
    def extract_text_and_boxes(
        cls,
        img: np.ndarray,
        image_hash: str = "",
        force_reprocess: bool = False
    ) -> List[OCRItem]:
        """
        Multilingual General OCR path:
        Detects all text lines (English & Urdu) and computes normalized coordinates.
        Uses disk caching for repeated invocations.
        """
        cache_key = cls.get_cache_key(image_hash, {"mode": "general", "langs": DEFAULT_OCR_LANGUAGES}) if image_hash else None
        cache_file = CACHE_DIR / f"ocr_{cache_key}.json" if cache_key else None

        if cache_file and cache_file.exists() and not force_reprocess:
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached_data = json.load(f)
                    return [OCRItem.from_dict(item) for item in cached_data]
            except Exception as e:
                logger.warning(f"Error reading OCR cache {cache_file}: {e}")

        reader = cls.get_reader()
        # Perform multilingual OCR
        results = reader.readtext(img)

        h, w = img.shape[:2]
        ocr_items: List[OCRItem] = []

        for bbox_pts, text, prob in results:
            clean_text = text.strip()
            if not clean_text:
                continue

            # Convert 4-point polygon to [x, y, width, height]
            pts = np.array(bbox_pts, dtype=np.int32)
            x_min = int(max(0, np.min(pts[:, 0])))
            y_min = int(max(0, np.min(pts[:, 1])))
            x_max = int(min(w, np.max(pts[:, 0])))
            y_max = int(min(h, np.max(pts[:, 1])))
            box_w = max(1, x_max - x_min)
            box_h = max(1, y_max - y_min)

            norm_bbox = [
                x_min / float(w),
                y_min / float(h),
                x_max / float(w),
                y_max / float(h)
            ]

            is_numeric = bool(re.search(r"\d", clean_text))

            item = OCRItem(
                text=clean_text,
                confidence=prob,
                bbox=[x_min, y_min, box_w, box_h],
                norm_bbox=norm_bbox,
                is_numeric=is_numeric
            )
            ocr_items.append(item)

        # Save to cache if image_hash is provided
        if cache_file:
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump([item.to_dict() for item in ocr_items], f, indent=2)
            except Exception as e:
                logger.warning(f"Failed to write OCR cache: {e}")

        return ocr_items

    @classmethod
    def read_numeric_region(
        cls,
        img: np.ndarray,
        bbox: Optional[List[int]] = None
    ) -> List[OCRItem]:
        """
        Dedicated Numeric OCR path:
        Restricts recognition strictly to NUMERIC_CHAR_WHITELIST ("0123456789.,-/: ")
        Runs on region of interest (ROI) to prevent alphanumeric misrecognition.
        """
        reader = cls.get_reader()
        h, w = img.shape[:2]

        if bbox is not None:
            x, y, bw, bh = bbox
            # Clamp to image dimensions
            x = max(0, min(x, w - 1))
            y = max(0, min(y, h - 1))
            bw = max(1, min(bw, w - x))
            bh = max(1, min(bh, h - y))
            roi = img[y : y + bh, x : x + bw]
            offset_x, offset_y = x, y
        else:
            roi = img
            offset_x, offset_y = 0, 0

        # Perform OCR with character whitelist
        results = reader.readtext(roi, allowlist=NUMERIC_CHAR_WHITELIST)
        numeric_items: List[OCRItem] = []

        roi_h, roi_w = roi.shape[:2]
        for bbox_pts, text, prob in results:
            clean_text = text.strip()
            if not clean_text:
                continue

            pts = np.array(bbox_pts, dtype=np.int32)
            x_min = int(max(0, np.min(pts[:, 0]))) + offset_x
            y_min = int(max(0, np.min(pts[:, 1]))) + offset_y
            x_max = int(min(w, np.max(pts[:, 0]) + offset_x))
            y_max = int(min(h, np.max(pts[:, 1]) + offset_y))
            box_w = max(1, x_max - x_min)
            box_h = max(1, y_max - y_min)

            norm_bbox = [
                x_min / float(w),
                y_min / float(h),
                x_max / float(w),
                y_max / float(h)
            ]

            numeric_items.append(OCRItem(
                text=clean_text,
                confidence=prob,
                bbox=[x_min, y_min, box_w, box_h],
                norm_bbox=norm_bbox,
                is_numeric=True
            ))

        return numeric_items
