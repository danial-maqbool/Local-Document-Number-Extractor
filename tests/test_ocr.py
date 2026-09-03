import numpy as np
import cv2
import pytest
from backend.services.ocr_service import OCRService, OCRItem

def test_number_normalization():
    raw = "O123S8l"
    normalized, mods = OCRService.normalize_numeric_string(raw)
    assert normalized == "0123581"
    assert len(mods) == 3
    assert any("O" in m and "0" in m for m in mods)
    assert any("S" in m and "5" in m for m in mods)
    assert any("l" in m and "1" in m for m in mods)

def test_ocr_item_serialization():
    item = OCRItem(
        text="98765432",
        confidence=0.9543,
        bbox=[10, 20, 100, 30],
        norm_bbox=[0.05, 0.1, 0.5, 0.25],
        is_numeric=True
    )
    d = item.to_dict()
    assert d["text"] == "98765432"
    assert d["is_numeric"] is True
    assert d["confidence"] == 0.9543

    recreated = OCRItem.from_dict(d)
    assert recreated.text == item.text
    assert recreated.norm_bbox == item.norm_bbox

def test_ocr_inference_on_synthetic_patch():
    # Create image with clear digits
    img = np.ones((120, 400, 3), dtype=np.uint8) * 255
    cv2.putText(img, "98452107", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 1.8, (0, 0, 0), 3)

    items = OCRService.extract_text_and_boxes(img)
    assert len(items) > 0
    extracted_texts = [it.text for it in items]
    assert any("98452107" in t for t in extracted_texts)

def test_numeric_region_ocr():
    img = np.ones((150, 400, 3), dtype=np.uint8) * 255
    cv2.putText(img, "45200.75", (30, 90), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 0), 3)

    num_items = OCRService.read_numeric_region(img, bbox=[20, 20, 350, 100])
    assert len(num_items) > 0
    clean_nums = "".join([it.text for it in num_items])
    assert "45200" in clean_nums
