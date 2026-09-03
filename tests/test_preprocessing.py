import cv2
import numpy as np
import pytest
from pathlib import Path
from backend.services.preprocessing import PreprocessingService
from backend.models.schemas import QualityStatus

@pytest.fixture
def temp_images_dir(tmp_path):
    d = tmp_path / "test_imgs"
    d.mkdir()
    return d

def test_hash_calculation(temp_images_dir):
    p = temp_images_dir / "sample.txt"
    p.write_bytes(b"hello document extraction")
    h1 = PreprocessingService.calculate_file_hash(p)
    h2 = PreprocessingService.calculate_file_hash(p)
    assert h1 == h2
    assert len(h1) == 64

def test_quality_analysis_sharp_image(temp_images_dir):
    # Create sharp synthetic image with high contrast grid
    img = np.ones((800, 600, 3), dtype=np.uint8) * 240
    # Add sharp text-like lines
    for y in range(50, 750, 40):
        cv2.putText(img, "TEST DOCUMENT 123456", (50, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    
    img_path = temp_images_dir / "sharp.jpg"
    PreprocessingService.save_image(img, img_path)
    
    report = PreprocessingService.analyze_quality(img)
    assert report.width == 600
    assert report.height == 800
    assert report.blur_score > 60.0
    assert report.status in [QualityStatus.GOOD, QualityStatus.REVIEW]

def test_quality_analysis_blurred_image(temp_images_dir):
    # Create blurry image with low Laplacian variance
    img = np.ones((600, 600, 3), dtype=np.uint8) * 128
    blurred = cv2.GaussianBlur(img, (51, 51), 30)
    report = PreprocessingService.analyze_quality(blurred)
    assert report.blur_score < 30.0
    assert report.status == QualityStatus.FAILED

def test_deskew_and_enhancement():
    img = np.ones((400, 400, 3), dtype=np.uint8) * 255
    cv2.putText(img, "SAMPLE DOCUMENT LINE", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 2)
    
    deskewed, angle = PreprocessingService.deskew_image(img)
    assert deskewed.shape == img.shape

    enhanced = PreprocessingService.enhance_contrast(img)
    assert enhanced.shape == img.shape

    shadowless = PreprocessingService.remove_shadows(img)
    assert shadowless.shape == img.shape

def test_preprocessing_pipeline(temp_images_dir):
    img = np.ones((600, 500, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (50, 50), (450, 550), (0, 0, 0), 2)
    cv2.putText(img, "ACCOUNT NO 98765432", (70, 100), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    
    img_path = temp_images_dir / "sample_doc.png"
    PreprocessingService.save_image(img, img_path)
    
    processed, quality, proc_path, meta = PreprocessingService.preprocess_pipeline(img_path)
    assert processed is not None
    assert proc_path.exists()
    assert "quality_status" in meta
