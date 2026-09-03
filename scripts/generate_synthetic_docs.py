"""
Local Document Number Extractor - Synthetic Test Dataset Generator
Generates 25 realistic synthetic phone-captured documents with English/Urdu labels,
geometric distortions, lighting variations, and strict ground truth.
"""
import os
import json
import random
import math
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

SYNTHETIC_DIR = Path("sample_data/synthetic")
SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
GROUND_TRUTH_FILE = SYNTHETIC_DIR / "ground_truth.json"

def apply_perspective_distortion(img: np.ndarray) -> np.ndarray:
    """Simulate phone perspective angle"""
    h, w = img.shape[:2]
    # Source points
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    # Target perturbed quadrilateral
    dx1 = random.randint(15, 35)
    dy1 = random.randint(10, 25)
    dx2 = random.randint(15, 35)
    dy2 = random.randint(10, 25)
    dst = np.float32([
        [dx1, dy1],
        [w - dx2, dy2],
        [w - random.randint(5, 20), h - random.randint(10, 30)],
        [random.randint(5, 20), h - random.randint(10, 30)]
    ])
    M = cv2.getPerspectiveTransform(src, dst)
    warped = cv2.warpPerspective(img, M, (w, h), borderValue=(235, 235, 235))
    return warped

def apply_shadow(img: np.ndarray) -> np.ndarray:
    """Simulate phone camera hand shadow casting a dark gradient"""
    h, w = img.shape[:2]
    mask = np.zeros((h, w), dtype=np.float32)
    # Circular or diagonal gradient
    cx, cy = random.randint(w // 4, 3 * w // 4), random.randint(h // 4, 3 * h // 4)
    y, x = np.ogrid[:h, :w]
    dist_from_center = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
    max_dist = np.sqrt(cx**2 + cy**2)
    mask = dist_from_center / max_dist
    mask = np.clip(mask, 0.35, 1.0)
    shadowed = (img.astype(np.float32) * mask[:, :, np.newaxis]).astype(np.uint8)
    return shadowed

def apply_rotation(img: np.ndarray, angle: float) -> np.ndarray:
    """Simulate document rotation"""
    h, w = img.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(img, M, (w, h), borderValue=(240, 240, 240))
    return rotated

def draw_electricity_bill(data: dict) -> np.ndarray:
    """Render a realistic utility electricity bill with English & Urdu labels"""
    w, h = 900, 1200
    img = np.ones((h, w, 3), dtype=np.uint8) * 255

    # Background subtle tint
    cv2.rectangle(img, (0, 0), (w, h), (248, 249, 250), -1)

    # Header banner
    cv2.rectangle(img, (40, 40), (w - 40, 130), (31, 78, 121), -1)
    cv2.putText(img, "ELECTRIC POWER DISTRIBUTION CO.", (60, 95), cv2.FONT_HERSHEY_DUPLEX, 1.0, (255, 255, 255), 2)
    cv2.putText(img, "ELECTRICITY CONSUMPTION BILL", (60, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 220, 240), 1)

    # Box 1: Account Information
    cv2.rectangle(img, (40, 150), (w - 40, 310), (180, 180, 180), 2)
    cv2.putText(img, "ACCOUNT INFORMATION / KHATA NUMBER", (55, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (31, 78, 121), 2)

    # Field 1: Account No
    cv2.putText(img, "Account No:", (60, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, str(data["Account Number"]), (260, 230), cv2.FONT_HERSHEY_DUPLEX, 0.9, (20, 20, 20), 2)

    # Field 2: Consumer ID
    cv2.putText(img, "Consumer ID:", (60, 280), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, str(data["Consumer ID"]), (260, 280), cv2.FONT_HERSHEY_DUPLEX, 0.9, (20, 20, 20), 2)

    # Box 2: Meter Readings
    cv2.rectangle(img, (40, 340), (w - 40, 620), (180, 180, 180), 2)
    cv2.putText(img, "METER READING DETAILS", (55, 375), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (31, 78, 121), 2)

    # Field 3: Previous Reading
    cv2.putText(img, "Previous Reading:", (60, 430), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, str(data["Previous Reading"]), (340, 430), cv2.FONT_HERSHEY_DUPLEX, 0.9, (20, 20, 20), 2)

    # Field 4: Current Reading
    cv2.putText(img, "Current Reading:", (60, 490), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, str(data["Current Reading"]), (340, 490), cv2.FONT_HERSHEY_DUPLEX, 0.9, (20, 20, 20), 2)

    # Field 5: Units
    cv2.putText(img, "Units Consumed:", (60, 560), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, str(data["Units"]), (340, 560), cv2.FONT_HERSHEY_DUPLEX, 0.9, (20, 20, 20), 2)

    # Box 3: Payment Summary
    cv2.rectangle(img, (40, 650), (w - 40, 850), (180, 180, 180), 2)
    cv2.rectangle(img, (45, 730), (w - 45, 840), (230, 240, 250), -1)
    # Field 6: Total Amount
    cv2.putText(img, "Total Amount Payable:", (60, 790), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (180, 0, 0), 2)
    cv2.putText(img, f"{data['Total Amount']:.2f}", (440, 790), cv2.FONT_HERSHEY_DUPLEX, 1.2, (180, 0, 0), 3)

    # Bottom notes
    cv2.putText(img, "Please pay before due date. For inquiries call helpline 118.", (60, 920), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 100, 100), 1)

    return img

def draw_invoice(data: dict) -> np.ndarray:
    """Render a commercial invoice"""
    w, h = 900, 1200
    img = np.ones((h, w, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (0, 0), (w, h), (250, 250, 250), -1)

    # Title
    cv2.putText(img, "TAX INVOICE / SALE BILL", (50, 80), cv2.FONT_HERSHEY_DUPLEX, 1.1, (20, 20, 20), 2)
    cv2.line(img, (50, 100), (w - 50, 100), (0, 0, 0), 2)

    # Invoice No
    cv2.putText(img, "Invoice Number:", (50, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, str(data["Invoice Number"]), (280, 160), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)

    # Table Header
    cv2.rectangle(img, (50, 220), (w - 50, 270), (220, 220, 220), -1)
    cv2.putText(img, "DESCRIPTION", (70, 255), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
    cv2.putText(img, "AMOUNT (PKR)", (650, 255), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)

    # Line item
    cv2.putText(img, "Professional Consulting Services", (70, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (40, 40, 40), 1)
    cv2.putText(img, f"{data['Subtotal']:.2f}", (650, 330), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    cv2.line(img, (50, 400), (w - 50, 400), (200, 200, 200), 1)

    # Subtotal
    cv2.putText(img, "Subtotal:", (450, 460), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, f"{data['Subtotal']:.2f}", (650, 460), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)

    # Tax
    cv2.putText(img, "Sales Tax Amount:", (450, 520), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(img, f"{data['Tax Amount']:.2f}", (650, 520), cv2.FONT_HERSHEY_DUPLEX, 0.9, (0, 0, 0), 2)

    # Grand Total
    cv2.rectangle(img, (430, 560), (w - 50, 630), (230, 245, 230), -1)
    cv2.putText(img, "Grand Total:", (450, 605), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 100, 0), 2)
    cv2.putText(img, f"{data['Grand Total']:.2f}", (650, 605), cv2.FONT_HERSHEY_DUPLEX, 1.1, (0, 100, 0), 3)

    return img

def generate_dataset():
    random.seed(42)
    np.random.seed(42)

    ground_truth = {}
    print("Generating 25 synthetic phone-captured test documents...")

    # 1. Generate 18 Electricity Bills
    for i in range(1, 19):
        acc_no = random.randint(10000000, 99999999)
        consumer_id = random.randint(1000000000, 9999999999)
        prev_read = random.randint(5000, 25000)
        units = random.randint(120, 650)
        curr_read = prev_read + units
        rate = random.uniform(22.0, 38.0)
        total_amt = round(units * rate + random.uniform(100, 500), 2)

        data = {
            "Account Number": acc_no,
            "Consumer ID": consumer_id,
            "Previous Reading": prev_read,
            "Current Reading": curr_read,
            "Units": units,
            "Total Amount": total_amt
        }

        filename = f"bill_doc_{i:02d}.jpg"
        img = draw_electricity_bill(data)

        # Apply realistic smartphone capture artifacts
        if i in [2, 7, 12]:
            # Rotated / skewed
            angle = random.choice([-5.0, -3.5, 4.0, 6.0])
            img = apply_rotation(img, angle)
        elif i in [3, 8, 14]:
            # Perspective distortion
            img = apply_perspective_distortion(img)
        elif i in [4, 9, 15]:
            # Shadow gradient
            img = apply_shadow(img)
        elif i in [5, 10]:
            # Mild blur
            img = cv2.GaussianBlur(img, (3, 3), 0.8)
        elif i == 18:
            # Severely blurry image to test FAILED quality detection
            img = cv2.GaussianBlur(img, (45, 45), 20)

        out_path = SYNTHETIC_DIR / filename
        cv2.imwrite(str(out_path), img)

        ground_truth[filename] = {
            "template_id": "electricity_bill",
            "expected_fields": data,
            "is_severe_blur": (i == 18)
        }
        print(f"Created {filename} (Electricity Bill)")

    # 2. Generate 7 Invoices
    for i in range(1, 8):
        inv_no = random.randint(10000, 99999)
        subtotal = round(random.uniform(5000, 45000), 2)
        tax = round(subtotal * 0.18, 2)
        grand_total = round(subtotal + tax, 2)

        data = {
            "Invoice Number": inv_no,
            "Subtotal": subtotal,
            "Tax Amount": tax,
            "Grand Total": grand_total
        }

        filename = f"invoice_doc_{i:02d}.jpg"
        img = draw_invoice(data)

        if i in [2, 4]:
            img = apply_rotation(img, random.choice([-4.0, 4.5]))
        elif i in [3, 5]:
            img = apply_shadow(img)

        out_path = SYNTHETIC_DIR / filename
        cv2.imwrite(str(out_path), img)

        ground_truth[filename] = {
            "template_id": "invoice",
            "expected_fields": data,
            "is_severe_blur": False
        }
        print(f"Created {filename} (Invoice)")

    with open(GROUND_TRUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(ground_truth, f, indent=2)

    print(f"\n[DONE] Generated {len(ground_truth)} synthetic documents with ground truth in {GROUND_TRUTH_FILE}")

if __name__ == "__main__":
    generate_dataset()
