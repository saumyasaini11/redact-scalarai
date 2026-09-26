import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_matches_generated_benchmark_and_rhp_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    benchmark = json.loads(
        (ROOT / "reports" / "benchmark" / "required_types_report.json").read_text(encoding="utf-8")
    )
    summary = json.loads((ROOT / "reports" / "summary_report.json").read_text(encoding="utf-8"))

    micro = benchmark["micro"]
    blocks = benchmark["block_classification"]
    assert f"| Precision | exact entity/span | {micro['precision']:.4f} |" in readme
    assert f"| Recall | exact entity/span | {micro['recall']:.4f} |" in readme
    assert f"| F1 | exact entity/span | {micro['f1']:.4f} |" in readme
    assert f"| Accuracy | binary text block | {blocks['accuracy']:.4f} |" in readme
    assert f"| Candidates | {summary['total_candidates']:,} |" in readme
    assert f"| Redacted/pseudonymized by policy | {summary['redacted_entities']:,} |" in readme
    assert f"| Protected corporate facts | {summary['protected_entities']:,} |" in readme
    assert summary["release_ready"] is True
    assert summary["qa_errors"] == []
