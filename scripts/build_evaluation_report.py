"""Generate the authoritative combined evaluation report from measured JSON evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_PATH = ROOT / "reports" / "benchmark" / "required_types_report.json"
SUMMARY_PATH = ROOT / "reports" / "summary_report.json"
OUTPUT_PATH = ROOT / "docs" / "EVALUATION_REPORT.md"


def _metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def build_report() -> Path:
    benchmark = json.loads(BENCHMARK_PATH.read_text(encoding="utf-8"))
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    micro = benchmark["micro"]
    blocks = benchmark["block_classification"]
    characters = benchmark["character_accuracy"]

    lines = [
        "# Final Evaluation Report",
        "",
        "This report is generated from `reports/benchmark/required_types_report.json` and "
        "`reports/summary_report.json`. It separates controlled benchmark metrics from "
        "full-document release QA.",
        "",
        "## 1. Evaluation scope",
        "",
        "The benchmark is a **frozen manually defined gold benchmark**, not independently "
        "annotated full-document ground truth. It contains one positive exact-span fixture for "
        "each assignment-required type and twelve explicit hard-negative blocks.",
        "",
        "Required types: `PERSON`, `EMAIL`, `PHONE`, `COMPANY`, `ADDRESS`, `SSN`, "
        "`CREDIT_CARD`, `DOB`, and `IPV4`.",
        "",
        "## 2. Exact entity/span results",
        "",
        "| Type | Support | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    required = set(benchmark["required_types"])
    for row in benchmark["rows"]:
        if row["pii_type"] not in required:
            continue
        lines.append(
            f"| {row['pii_type']} | {row['support']} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{_metric(row['precision'])} | {_metric(row['recall'])} | {_metric(row['f1'])} |"
        )

    lines.extend([
        "",
        "### Exact-span aggregate",
        "",
        f"- TP: **{micro['tp']}**",
        f"- FP: **{micro['fp']}**",
        f"- FN: **{micro['fn']}**",
        f"- Precision: **{_metric(micro['precision'])}**",
        f"- Recall: **{_metric(micro['recall'])}**",
        f"- F1: **{_metric(micro['f1'])}**",
        "",
        "Entity-level TN is not reported because arbitrary non-entity spans are not a finite "
        "classification unit.",
        "",
        "## 3. Block-level classification",
        "",
        f"Unit: **{blocks['unit']}**.",
        "",
        "| TP | TN | FP | FN | Accuracy | Precision | Recall | F1 |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|",
        f"| {blocks['tp']} | {blocks['tn']} | {blocks['fp']} | {blocks['fn']} | "
        f"{_metric(blocks['accuracy'])} | {_metric(blocks['precision'])} | "
        f"{_metric(blocks['recall'])} | {_metric(blocks['f1'])} |",
        "",
        "Formulas:",
        "",
        "- Accuracy = `(TP + TN) / (TP + TN + FP + FN)`",
        "- Precision = `TP / (TP + FP)`",
        "- Recall = `TP / (TP + FN)`",
        "- F1 = `2 × Precision × Recall / (Precision + Recall)`",
        "",
        "## 4. Additional character metric",
        "",
        f"Character TP/TN/FP/FN: **{characters['tpchar']} / {characters['tnchar']} / "
        f"{characters['fpchar']} / {characters['fnchar']}**. Character accuracy: "
        f"**{_metric(characters['accuracy'])}**.",
        "",
        "Character accuracy is additional coverage evidence and is not called classification accuracy.",
        "",
        "## 5. Full RHP release QA",
        "",
        "The prospectus does not have full-document gold annotations, so full-document accuracy, "
        "precision, recall and F1 are **not claimed**. The following are release/QA measurements:",
        "",
        "| Check | Result |",
        "|---|---:|",
        f"| Candidates | {summary['total_candidates']:,} |",
        f"| Redacted/pseudonymized | {summary['redacted_entities']:,} |",
        f"| Protected corporate facts | {summary['protected_entities']:,} |",
        f"| Unresolved policy-review items | {summary['unresolved_review_items']} |",
        f"| Sensitive media replaced | {summary['media_replaced']} / {summary['media_total']} |",
        f"| Source/output text blocks | {summary['source_text_blocks']} / {summary['output_text_blocks']} |",
        f"| Structure signature preserved | {summary['structure_preserved']} |",
        f"| Replacement application failures | {summary['replacement_application_failures']} |",
        f"| Residual approved originals | {summary['residual_approved_originals_at_release']} |",
        f"| Automated QA findings | {len(summary['qa_errors'])} |",
        f"| Release gate | {'PASS' if summary['release_ready'] else 'FAIL'} |",
        "",
        f"Output SHA-256: `{summary['output_sha256']}`.",
        "",
        f"Final DOCX: `{summary['output_path'].replace(chr(92), '/')}`.",
        "",
        "Corporate facts are detected separately from policy. The real RHP uses company "
        "protection, while the controlled benchmark still evaluates COMPANY detection.",
        "",
        "## 6. Limitations",
        "",
        "- A 100% controlled-benchmark score does not imply 100% performance on unseen documents.",
        "- spaCy and OCR can still produce false positives or miss fragmented/low-quality text.",
        "- Unsupported drawing/text-box encodings may not be represented as ordinary OOXML text blocks.",
        "- A larger independently annotated RHP sample is the next meaningful evaluation step.",
        "",
        "Machine-readable details are in `reports/benchmark/required_types_evaluation.csv`, "
        "`reports/benchmark/required_types_report.json`, `reports/rhp_release_validation.csv`, "
        "and `reports/summary_report.json`.",
    ])
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return OUTPUT_PATH


def main() -> int:
    path = build_report()
    print(f"Generated {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
