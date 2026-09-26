from pathlib import Path
from uuid import uuid4

from pii_redactor.benchmark import REQUIRED_PII_TYPES, run_required_type_benchmark


def test_required_type_benchmark_has_real_metrics_and_full_coverage():
    tmp_path = Path(".tmp") / f"benchmark-{uuid4().hex}"
    report = run_required_type_benchmark(tmp_path)
    assert report["status"] == "COMPLETE"
    assert report["all_required_types_detected"] is True
    assert len(REQUIRED_PII_TYPES) == 9
    assert report["micro"]["tp"] == 9
    assert report["micro"]["fp"] == 0
    assert report["micro"]["recall"] == 1.0
    classification = report["block_classification"]
    assert classification == {
        "unit": "text block (binary: contains any labeled PII)",
        "support": 21,
        "tp": 9,
        "tn": 12,
        "fp": 0,
        "fn": 0,
        "accuracy": 1.0,
        "precision": 1.0,
        "recall": 1.0,
        "f1": 1.0,
    }
