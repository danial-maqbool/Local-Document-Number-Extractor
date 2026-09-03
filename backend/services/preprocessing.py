"""
Local Document Number Extractor - Image Preprocessing Service
Comprehensive computer vision preprocessing pipeline for phone-captured document photographs.
"""
import cv2
import numpy as np
from pathlib import Path
from typing import Tuple, Optional, Dict, Any, List
import hashlib
import logging

from backend.config import (
    QUALITY_BLUR_THRESHOLD_FAILED, QUALITY_BLUR_THRESHOLD_REVIEW,
    QUALITY_MIN_WIDTH, QUALITY_MIN_HEIGHT,
    QUALITY_BRIGHTNESS_MIN, QUALITY_BRIGHTNESS_MAX, QUALITY_CONTRAST_MIN,
    PROCESSED_DIR, CACHE_DIR
)
from backend.models.schemas import QualityReport, QualityStatus

logger = logging.getLogger("extractor.preprocessing")

class PreprocessingService:
    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """Compute SHA-256 hash of an image file for duplicate detection and caching"""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def load_image(image_path: Path) -> np.ndarray:
        """Load image from disk handling unicode paths on Windows safely"""
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        with open(image_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), dtype=np.uint8)
            img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            
        if img is None:
            raise ValueError(f"Failed to decode image from {image_path}")
        return img

    @staticmethod
    def save_image(img: np.ndarray, output_path: Path) -> Path:
        """Save image to disk safely supporting Windows path encoding"""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        ext = output_path.suffix.lower() or ".jpg"
        success, encoded_img = cv2.imencode(ext, img)
        if not success:
            raise IOError(f"Failed to encode image for saving to {output_path}")
        with open(output_path, "wb") as f:
            f.write(encoded_img)
        return output_path

    @classmethod
    def analyze_quality(cls, img: np.ndarray) -> QualityReport:
        """
        Analyze image quality metrics:
        - Blur score (Variance of Laplacian)
        - Brightness (Mean grayscale intensity)
        - Contrast (Standard deviation of intensity)
        - Dimensions (Width, Height)
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img

        laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        
        issues = []
        status = QualityStatus.GOOD

        if w < QUALITY_MIN_WIDTH or h < QUALITY_MIN_HEIGHT:
            issues.append(f"Low image resolution: {w}x{h}")
            status = QualityStatus.FAILED

        if laplacian_var < QUALITY_BLUR_THRESHOLD_FAILED:
            issues.append(f"Critical blur detected (Laplacian variance {laplacian_var:.1f})")
            status = QualityStatus.FAILED
        elif laplacian_var < QUALITY_BLUR_THRESHOLD_REVIEW:
            issues.append(f"Noticeable blur detected (Laplacian variance {laplacian_var:.1f})")
            if status != QualityStatus.FAILED:
                status = QualityStatus.REVIEW

        if brightness < QUALITY_BRIGHTNESS_MIN:
            issues.append(f"Image is severely underexposed / dark (brightness {brightness:.1f})")
            if status == QualityStatus.GOOD:
                status = QualityStatus.LOW_QUALITY
        elif brightness > QUALITY_BRIGHTNESS_MAX:
            issues.append(f"Image is severely overexposed / washed out (brightness {brightness:.1f})")
            if status == QualityStatus.GOOD:
                status = QualityStatus.LOW_QUALITY

        if contrast < QUALITY_CONTRAST_MIN:
            issues.append(f"Low dynamic contrast (contrast {contrast:.1f})")
            if status == QualityStatus.GOOD:
                status = QualityStatus.REVIEW

        return QualityReport(
            blur_score=round(laplacian_var, 2),
            brightness=round(brightness, 2),
            contrast=round(contrast, 2),
            width=w,
            height=h,
            coverage_score=1.0,
            status=status,
            issues=issues
        )

    @classmethod
    def detect_document_contour(cls, img: np.ndarray) -> Optional[np.ndarray]:
        """
        Detect largest quadrilateral contour representing the document boundary.
        Returns 4 points of the corner polygon if found and valid.
        """
        h, w = img.shape[:2]
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        scale = 800.0 / max(h, w) if max(h, w) > 800 else 1.0
        if scale != 1.0:
            small_gray = cv2.resize(gray, (int(w * scale), int(h * scale)))
        else:
            small_gray = gray

        blurred = cv2.GaussianBlur(small_gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, kernel)

        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        image_area = small_gray.shape[0] * small_gray.shape[1]
        for c in contours[:5]:
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.02 * peri, True)
            area = cv2.contourArea(approx)

            if len(approx) == 4 and area > 0.25 * image_area:
                pts = approx.reshape(4, 2).astype(np.float32)
                if scale != 1.0:
                    pts /= scale
                return pts
        return None

    @staticmethod
    def order_points(pts: np.ndarray) -> np.ndarray:
        """Order points in top-left, top-right, bottom-right, bottom-left sequence"""
        rect = np.zeros((4, 2), dtype=np.float32)
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # top-left
        rect[2] = pts[np.argmax(s)]  # bottom-right

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)] # top-right
        rect[3] = pts[np.argmax(diff)] # bottom-left
        return rect

    @classmethod
    def warp_perspective(cls, img: np.ndarray, pts: np.ndarray) -> np.ndarray:
        """Apply 4-point perspective transform to extract flat rectangular document"""
        rect = cls.order_points(pts)
        (tl, tr, br, bl) = rect

        width_a = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_b = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_width = max(int(width_a), int(width_b))

        height_a = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_b = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_height = max(int(height_a), int(height_b))

        if max_width < 100 or max_height < 100:
            return img

        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ], dtype=np.float32)

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(img, M, (max_width, max_height), flags=cv2.INTER_LINEAR)
        return warped

    @staticmethod
    def deskew_image(img: np.ndarray, max_angle: float = 30.0) -> Tuple[np.ndarray, float]:
        """
        Estimate skew angle from text line orientations using minAreaRect and rotate back
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
        
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 9
        )
        coords = np.column_stack(np.where(thresh > 0))
        if len(coords) < 100:
            return img, 0.0

        angle = cv2.minAreaRect(coords)[-1]
        if angle < -45:
            angle = -(90 + angle)
        elif angle > 45:
            angle = 90 - angle
        else:
            angle = -angle

        if abs(angle) < 0.5 or abs(angle) > max_angle:
            return img, 0.0

        h, w = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        return rotated, angle

    @staticmethod
    def remove_shadows(img: np.ndarray) -> np.ndarray:
        """Remove phone shadows using morphological illumination background division"""
        if len(img.shape) == 3:
            planes = cv2.split(img)
            result_planes = []
            for plane in planes:
                dilated_img = cv2.dilate(plane, np.ones((7, 7), np.uint8))
                bg_img = cv2.medianBlur(dilated_img, 21)
                diff_img = 255 - cv2.absdiff(plane, bg_img)
                norm_img = cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)
                result_planes.append(norm_img)
            return cv2.merge(result_planes)
        else:
            dilated_img = cv2.dilate(img, np.ones((7, 7), np.uint8))
            bg_img = cv2.medianBlur(dilated_img, 21)
            diff_img = 255 - cv2.absdiff(img, bg_img)
            return cv2.normalize(diff_img, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8UC1)

    @staticmethod
    def enhance_contrast(img: np.ndarray) -> np.ndarray:
        """Enhance local document contrast using CLAHE"""
        if len(img.shape) == 3:
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            cl = clahe.apply(l)
            limg = cv2.merge((cl, a, b))
            return cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(img)

    @staticmethod
    def denoise_and_sharpen(img: np.ndarray) -> np.ndarray:
        """Denoise with bilateral filter and apply mild unsharp masking to enhance text strokes"""
        denoised = cv2.bilateralFilter(img, d=5, sigmaColor=50, sigmaSpace=50)
        gaussian = cv2.GaussianBlur(denoised, (0, 0), 2.0)
        sharpened = cv2.addWeighted(denoised, 1.25, gaussian, -0.25, 0)
        return sharpened

    @classmethod
    def preprocess_pipeline(
        cls,
        image_path: Path,
        output_prefix: str = "proc"
    ) -> Tuple[np.ndarray, QualityReport, Path, Dict[str, Any]]:
        """
        Full end-to-end preprocessing pipeline:
        1. Load image safely
        2. Analyze quality metrics
        3. Detect document contour & warp perspective if found
        4. Deskew
        5. Remove shadows & enhance contrast (CLAHE)
        6. Denoise and sharpen
        7. Save processed image into PROCESSED_DIR
        """
        img = cls.load_image(image_path)
        quality = cls.analyze_quality(img)

        metadata = {
            "original_dimensions": (quality.width, quality.height),
            "perspective_corrected": False,
            "skew_angle": 0.0,
            "quality_status": quality.status.value
        }

        pts = cls.detect_document_contour(img)
        if pts is not None:
            processed = cls.warp_perspective(img, pts)
            metadata["perspective_corrected"] = True
        else:
            processed = img.copy()

        processed, skew_angle = cls.deskew_image(processed)
        metadata["skew_angle"] = round(skew_angle, 2)

        processed = cls.remove_shadows(processed)
        processed = cls.enhance_contrast(processed)
        processed = cls.denoise_and_sharpen(processed)

        file_hash = cls.calculate_file_hash(image_path)
        output_name = f"{output_prefix}_{file_hash[:12]}_{image_path.name}"
        processed_path = PROCESSED_DIR / output_name
        cls.save_image(processed, processed_path)

        return processed, quality, processed_path, metadata
