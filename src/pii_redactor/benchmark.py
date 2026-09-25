from __future__ import annotations

import json
from pathlib import Path

from .ensemble import merge_and_score
from .evaluation import evaluate, write_evaluation
from .models import PIIType, TextBlock
from .recognizers import detect_all


REQUIRED_PII_TYPES = (
    PIIType.PERSON,
    PIIType.EMAIL,
    PIIType.PHONE,
    PIIType.ADDRESS,
    PIIType.COMPANY,
    PIIType.DOB,
    PIIType.SSN,
    PIIType.CREDIT_CARD,
    PIIType.IPV4,
)

FIXTURES = (
    (PIIType.PERSON, "Contact person: John Smith", "John Smith"),
    (PIIType.EMAIL, "Email: reviewer.quality@example.test", "reviewer.quality@example.test"),
    (PIIType.PHONE, "Telephone: +91 98765 43210", "+91 98765 43210"),
    (PIIType.ADDRESS, "Address: 42 Example Road, Sample Nagar, Delhi 110001", "42 Example Road, Sample Nagar, Delhi 110001"),
    (PIIType.COMPANY, "Company: Example Technologies Private Limited", "Example Technologies Private Limited"),
    (PIIType.DOB, "Date of birth: 14/03/1987", "14/03/1987"),
    (PIIType.SSN, "SSN: 123-45-6789", "123-45-6789"),
    (PIIType.CREDIT_CARD, "Payment card: 4111 1111 1111 1111", "4111 1111 1111 1111"),
    (PIIType.IPV4, "Client IP: 192.168.1.10", "192.168.1.10"),
)

HARD_NEGATIVES = (
    "Board meeting held on December 10, 2025",
    "Aggregate offer size is INR 7,100 million",
    "Order 123456 remains open",
    "See Page 124 for additional details",
)


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def run_required_type_benchmark(
    output_dir: Path,
    *,
    default_region: str = "IN",
    spacy_model: str = "en_core_web_md",
) -> dict:
    """Run the production detector on a frozen, independently labeled nine-type corpus."""
    output_dir.mkdir(parents=True, exist_ok=True)
    blocks: list[TextBlock] = []
    gold: list[dict] = []
    manifest: list[dict] = []
    for index, (pii_type, text, value) in enumerate(FIXTURES, start=1):
        block_id = f"benchmark#p{index}"
        start = text.index(value)
        end = start + len(value)
        blocks.append(TextBlock(block_id, "benchmark/document.xml", text, index))
        gold.append({
            "pii_type": pii_type.value,
            "document_part": "benchmark/document.xml",
            "block_id": block_id,
            "start_offset": start,
            "end_offset": end,
            "source_kind": "native_text",
        })
        manifest.append({
            "document_part": "benchmark/document.xml",
            "block_id": block_id,
            "text": text,
        })
    negative_block_ids: list[str] = []
    for offset, text in enumerate(HARD_NEGATIVES, start=len(FIXTURES) + 1):
        block_id = f"benchmark#p{offset}"
        negative_block_ids.append(block_id)
        blocks.append(TextBlock(block_id, "benchmark/document.xml", text, offset))
        manifest.append({"document_part": "benchmark/document.xml", "block_id": block_id, "text": text})
    gold_path = output_dir / "required_types_gold.jsonl"
    manifest_path = output_dir / "required_types_manifest.jsonl"
    _write_jsonl(gold_path, gold)
    _write_jsonl(manifest_path, manifest)

    predictions = merge_and_score(
        detect_all(blocks, default_region, spacy_model),
        high_threshold=0.85,
        medium_threshold=0.60,
    )
    report = evaluate(predictions, gold_path, manifest_path)
    predicted_types = {item.pii_type.value for item in predictions}
    report["benchmark_scope"] = "Frozen controlled corpus with one labeled example for each required PII type"
    report["required_types"] = [item.value for item in REQUIRED_PII_TYPES]
    report["required_type_coverage"] = {
        item.value: item.value in predicted_types for item in REQUIRED_PII_TYPES
    }
    report["all_required_types_detected"] = all(report["required_type_coverage"].values())
    negative_hits = {block_id: 0 for block_id in negative_block_ids}
    for prediction in predictions:
        if prediction.block_id in negative_hits:
            negative_hits[prediction.block_id] += 1
    report["negative_controls"] = {
        "blocks": len(negative_block_ids),
        "true_negative_blocks": sum(value == 0 for value in negative_hits.values()),
        "false_positive_blocks": sum(value > 0 for value in negative_hits.values()),
        "false_positive_entities": sum(negative_hits.values()),
    }
    (output_dir / "required_types_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    write_evaluation(
        report,
        output_dir / "required_types_evaluation.md",
        output_dir / "required_types_evaluation.csv",
        title="Required PII Types Benchmark",
        scope_note=(
            "These are measured exact-span results on a frozen controlled benchmark. "
            "They prove executable coverage of the nine required types, but they do not substitute "
            "for full-corpus metrics on an uploaded document unless that document has independent gold annotations."
        ),
    )
    return report
