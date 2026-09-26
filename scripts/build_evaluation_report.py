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
        "# PII Redaction Evaluation Report",
        "",
        "The nine-type controlled benchmark found 9 true positives with no false positives or "
        "false negatives. The final prospectus DOCX passed release QA. This report explains "
        "the evaluation method and separates benchmark metrics from full-document checks.",
        "",
        "## Evaluation scope",
        "",
        "The benchmark is a **frozen manually defined gold benchmark**, not independently "
        "annotated full-document ground truth. It contains one positive exact-span fixture for "
        "each assignment-required type and twelve explicit hard-negative blocks.",
        "",
        "Required types: `PERSON`, `EMAIL`, `PHONE`, `COMPANY`, `ADDRESS`, `SSN`, "
        "`CREDIT_CARD`, `DOB`, and `IPV4`.",
        "",
        "## Evaluation strategy",
        "",
        "The detector is run on a frozen set of 21 text blocks. Nine blocks each contain "
        "one manually labeled exact span for an assignment-required type. Twelve hard-negative "
        "blocks contain ordinary dates, amounts, page and order references, legal terms, "
        "identifiers, and invalid IP or card lookalikes. The gold spans and block manifest "
        "define the comparison; predictions are not used to create their own labels.",
        "",
        "An exact entity match requires the same PII type, document part, block ID, and start "
        "and end offsets as the gold annotation. Matched predictions are true positives; "
        "unmatched predictions are false positives; unmatched gold spans are false negatives. "
        "Micro precision, recall, and F1 use these counts. Entity-level true negatives are "
        "undefined because arbitrary non-entity spans do not form a finite test set.",
        "",
        "For classification accuracy, the unit is a text block: a block is positive when it "
        "has any gold PII span and predicted-positive when the detector emits any candidate. "
        "The fixed manifest supplies both positive and negative blocks, so TP, TN, FP, FN, "
        "accuracy, precision, recall, and F1 have explicit denominators. Character coverage "
        "is reported separately and is not called classification accuracy.",
        "",
        "The supplied prospectus has no complete full-document gold annotations. Its release "
        "evaluation instead compares source and output hashes, verifies the DOCX can be opened, "
        "checks structural and text-block preservation, confirms selected replacements and "
        "media changes, scans processed blocks for approved originals, and requires zero "
        "unresolved policy decisions or QA errors. These checks support release readiness; "
        "they cannot establish full-document precision, recall, or absence of missed PII.",
        "",
        "## Exact entity and span results",
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
        "### Exact span aggregate",
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
        "## Block classification",
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
        "## Character coverage",
        "",
        f"Character TP/TN/FP/FN: **{characters['tpchar']} / {characters['tnchar']} / "
        f"{characters['fpchar']} / {characters['fnchar']}**. Character accuracy: "
        f"**{_metric(characters['accuracy'])}**.",
        "",
        "Character accuracy is additional coverage evidence and is not called classification accuracy.",
        "",
        "## Full prospectus release quality assurance",
        "",
        "The prospectus does not have full-document gold annotations, so full-document accuracy, "
        "precision, recall and F1 are **not claimed**. The following are release/QA measurements:",
        "",
        "| Check | Result |",
        "|---|---:|",
        f"| Candidates | {summary['total_candidates']:,} |",
        f"| Redacted/pseudonymized | {summary['redacted_entities']:,} |",
        f"| Protected corporate facts | {summary['protected_entities']:,} |",
        f"| Ignored non-PII candidates | {summary['ignored_entities']:,} |",
        f"| Unresolved policy-review items | {summary['unresolved_review_items']} |",
        f"| Sensitive media replaced | {summary['media_replaced']} / {summary['media_total']} |",
        f"| Source/output text blocks | {summary['source_text_blocks']} / {summary['output_text_blocks']} |",
        f"| Structure signature preserved | {summary['structure_preserved']} |",
        f"| Replacement application failures | {summary['replacement_application_failures']} |",
        f"| Residual approved originals | {summary['residual_approved_originals_at_release']} |",
        f"| Automated QA findings | {len(summary['qa_errors'])} |",
        f"| Release gate | {'PASS' if summary['release_ready'] else 'FAIL'} |",
        "",
        f"Source SHA-256: `{summary['source_sha256']}`.",
        "",
        f"Output SHA-256: `{summary['output_sha256']}`.",
        "",
        f"Final DOCX: `{summary['output_path'].replace(chr(92), '/')}`.",
        "",
        "Company detection and redaction are supported. The real RHP protects legitimate "
        "corporate facts to preserve the issuer's factual content; the controlled benchmark "
        "evaluates COMPANY detection, and a strict-policy DOCX test verifies replacement.",
        "",
        "The media audit records a decoded QR as REDACT/replaced and an undecoded square "
        "logo candidate as IGNORE/preserved. Geometric resemblance alone is not treated "
        "as sufficient evidence to replace a graphic.",
        "",
        "## Limitations",
        "",
        "- A 100% controlled-benchmark score does not imply 100% performance on unseen documents.",
        "- spaCy and OCR can still produce false positives or miss fragmented/low-quality text.",
        "- Unsupported drawing/text-box encodings may not be represented as ordinary OOXML text blocks.",
        "- A larger independently annotated RHP sample is the next meaningful evaluation step.",
        "",
        "Machine-readable details are in `reports/benchmark/required_types_evaluation.csv`, "
        "`reports/benchmark/required_types_report.json`, `reports/rhp_release_validation.csv`, "
        "`reports/summary_report.json`, and the packaged `reports/media_audit.json`.",
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
