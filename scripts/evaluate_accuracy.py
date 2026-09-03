"""
Local Document Number Extractor - Benchmark & Accuracy Evaluation Tool
Computes empirical metrics against synthetic ground truth:
- Field Accuracy (Overall & Per-Field)
- Complete Document Accuracy
- Character Accuracy
- Missing Field Rate
- False Extraction Rate
- Manual Review Rate
"""
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import json
import logging
from difflib import SequenceMatcher

from backend.config import TEMPLATES_DIR, BASE_DIR
from backend.models.schemas import DocumentTemplate, ExtractionStatus
from backend.services.batch_service import BatchService

logging.basicConfig(level=logging.WARNING)

def char_similarity(s1: str, s2: str) -> float:
    return SequenceMatcher(None, str(s1).strip(), str(s2).strip()).ratio()

def evaluate():
    gt_file = Path("sample_data/synthetic/ground_truth.json")
    if not gt_file.exists():
        print(f"Ground truth file not found: {gt_file}")
        sys.exit(1)

    with open(gt_file, "r", encoding="utf-8") as f:
        ground_truth = json.load(f)

    templates = {}
    for t_id in ["electricity_bill", "invoice"]:
        t_path = TEMPLATES_DIR / f"{t_id}.json"
        with open(t_path, "r", encoding="utf-8") as tf:
            templates[t_id] = DocumentTemplate(**json.load(tf))

    batch_service = BatchService()

    total_docs = len(ground_truth)
    fully_correct_docs = 0
    docs_needing_review = 0
    total_expected_fields = 0
    correctly_extracted_fields = 0
    missing_fields = 0
    false_extractions = 0
    total_char_accuracy = 0.0

    per_field_stats = {}

    print(f"Running comprehensive evaluation on {total_docs} ground-truth test documents...")
    print("=" * 70)

    for filename, gt_info in ground_truth.items():
        img_path = Path("sample_data/synthetic") / filename
        template_id = gt_info["template_id"]
        template = templates[template_id]
        expected_fields = gt_info["expected_fields"]

        res = batch_service.process_single_document(img_path, template, force_reprocess=True)

        if res.status in [ExtractionStatus.REVIEW, ExtractionStatus.FAILED]:
            docs_needing_review += 1

        doc_all_correct = True

        for fname, exp_val in expected_fields.items():
            total_expected_fields += 1
            if fname not in per_field_stats:
                per_field_stats[fname] = {"total": 0, "correct": 0}
            per_field_stats[fname]["total"] += 1

            extracted_item = res.fields.get(fname)
            ext_val = extracted_item.value if extracted_item else None

            if ext_val is None:
                missing_fields += 1
                doc_all_correct = False
            else:
                match = False
                if isinstance(exp_val, float) or isinstance(ext_val, float):
                    try:
                        match = abs(float(exp_val) - float(ext_val)) < 0.1
                    except (ValueError, TypeError):
                        match = False
                else:
                    match = (str(exp_val).strip() == str(ext_val).strip())

                char_acc = char_similarity(str(exp_val), str(ext_val))
                total_char_accuracy += char_acc

                if match:
                    correctly_extracted_fields += 1
                    per_field_stats[fname]["correct"] += 1
                else:
                    false_extractions += 1
                    doc_all_correct = False

        if doc_all_correct and not gt_info.get("is_severe_blur", False):
            fully_correct_docs += 1

        status_str = f"[{res.status.value}]"
        print(f"{filename:<22} {status_str:<10} Confidence: {res.overall_confidence:.2f}")

    overall_field_acc = (correctly_extracted_fields / total_expected_fields * 100) if total_expected_fields > 0 else 0
    doc_acc = (fully_correct_docs / total_docs * 100) if total_docs > 0 else 0
    avg_char_acc = (total_char_accuracy / (total_expected_fields - missing_fields) * 100) if (total_expected_fields - missing_fields) > 0 else 0
    missing_rate = (missing_fields / total_expected_fields * 100) if total_expected_fields > 0 else 0
    false_ext_rate = (false_extractions / total_expected_fields * 100) if total_expected_fields > 0 else 0
    review_rate = (docs_needing_review / total_docs * 100) if total_docs > 0 else 0

    print("=" * 70)
    print("EXTRACTION ACCURACY BENCHMARK REPORT")
    print("=" * 70)
    print(f"Total Documents Tested:         {total_docs}")
    print(f"Complete Document Accuracy:     {doc_acc:.2f}%")
    print(f"Overall Field Accuracy:         {overall_field_acc:.2f}%")
    print(f"Character-Level Accuracy:       {avg_char_acc:.2f}%")
    print(f"Missing Field Rate:             {missing_rate:.2f}%")
    print(f"False Extraction Rate:          {false_ext_rate:.2f}%")
    print(f"Manual Review Rate:             {review_rate:.2f}%")
    print("-" * 70)
    print("Per-Field Accuracy Breakdown:")
    for fname, stats in sorted(per_field_stats.items()):
        acc = (stats["correct"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  * {fname:<25}: {acc:5.1f}% ({stats['correct']}/{stats['total']})")
    print("=" * 70)

    eval_report = {
        "total_documents": total_docs,
        "document_accuracy_pct": round(doc_acc, 2),
        "overall_field_accuracy_pct": round(overall_field_acc, 2),
        "character_accuracy_pct": round(avg_char_acc, 2),
        "missing_field_rate_pct": round(missing_rate, 2),
        "false_extraction_rate_pct": round(false_ext_rate, 2),
        "manual_review_rate_pct": round(review_rate, 2),
        "per_field_accuracy": {
            k: round(v["correct"] / v["total"] * 100, 2) for k, v in per_field_stats.items()
        }
    }
    with open("sample_data/synthetic/evaluation_report.json", "w", encoding="utf-8") as f:
        json.dump(eval_report, f, indent=2)

if __name__ == "__main__":
    evaluate()
