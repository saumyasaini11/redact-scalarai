import json
from pathlib import Path

from pii_redactor.evaluation import evaluate
from pii_redactor.models import PIIRecord, PIIType, PolicyAction, ReviewStatus


def _record(record_id: str, start: int, end: int) -> PIIRecord:
    return PIIRecord(
        record_id=record_id,
        pii_type=PIIType.EMAIL,
        original_text="x@example.com",
        normalized_text="x@example.com",
        source_kind="native_text",
        document_part="word/document.xml",
        block_id="block-1",
        start_offset=start,
        end_offset=end,
        final_confidence=0.95,
    )


def test_strict_and_relaxed_evaluation():
    work = Path(".tmp")
    work.mkdir(exist_ok=True)
    gold_path = work / "test-evaluation-gold.jsonl"
    manifest_path = work / "test-evaluation-manifest.jsonl"
    gold_path.write_text(json.dumps({
        "pii_type": "EMAIL", "document_part": "word/document.xml",
        "block_id": "block-1", "start_offset": 0, "end_offset": 13,
        "source_kind": "native_text",
    }) + "\n", encoding="utf-8")
    manifest_path.write_text(json.dumps({
        "document_part": "word/document.xml", "block_id": "block-1", "text": "x@example.com text",
    }) + "\n", encoding="utf-8")
    try:
        report = evaluate([_record("x", 0, 13)], gold_path, manifest_path)
        assert report["micro"]["tp"] == 1
        assert report["micro"]["f1"] == 1.0
        assert report["block_classification"]["tp"] == 1
        assert report["block_classification"]["tn"] == 0
        assert report["block_classification"]["accuracy"] == 1.0
        assert report["character_accuracy"]["accuracy"] == 1.0
    finally:
        gold_path.unlink(missing_ok=True)
        manifest_path.unlink(missing_ok=True)


def test_release_gate_uses_policy_action_not_confidence_flag():
    missing = Path(".tmp") / "missing-gold.jsonl"
    prediction = _record("company", 0, 13)
    prediction.review_status = ReviewStatus.NEEDS_REVIEW
    prediction.policy_action = PolicyAction.PROTECT
    report = evaluate([prediction], missing)
    assert report["unresolved_count"] == 0
    assert report["release_gate_passed"] is True
    assert report["policy_counts"] == {"PROTECT": 1}
