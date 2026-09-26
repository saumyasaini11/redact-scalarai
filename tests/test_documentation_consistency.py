import json
from pathlib import Path

from pii_redactor.models import ASSIGNMENT_PII_TYPES


ROOT = Path(__file__).resolve().parents[1]


def test_readme_matches_generated_benchmark_and_rhp_summary():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    evaluation = (ROOT / "docs" / "EVALUATION_REPORT.md").read_text(encoding="utf-8")
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
    assert f"- Precision: **{micro['precision']:.4f}**" in evaluation
    assert f"- Recall: **{micro['recall']:.4f}**" in evaluation
    assert f"| {blocks['tp']} | {blocks['tn']} | {blocks['fp']} | {blocks['fn']} |" in evaluation
    assert f"| Candidates | {summary['total_candidates']:,} |" in readme
    assert f"| Redacted/pseudonymized by policy | {summary['redacted_entities']:,} |" in readme
    assert f"| Protected corporate facts | {summary['protected_entities']:,} |" in readme
    assert summary["release_ready"] is True
    assert summary["qa_errors"] == []
    assert f"Output SHA-256: `{summary['output_sha256']}`" in evaluation
    final_name = "Red Herring Prospectus - Pseudonymized.docx"
    assert final_name in readme
    assert final_name in evaluation


def test_ui_wording_and_sensitive_media_default_match_documentation():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    config = (ROOT / "config.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert '"Optional gold annotations"' in app
    assert "independent gold annotations" not in app.casefold()
    assert "unless gold annotations are supplied" in app
    assert '"High-security mode: replace all embedded media"' in app
    assert "value=False" in app
    assert "replace_all_media = false" in config
    assert "sensitive-media-only" in readme


def test_rhp_reports_show_all_assignment_types_with_actual_counts():
    summary = json.loads((ROOT / "reports" / "summary_report.json").read_text(encoding="utf-8"))
    qa = (ROOT / "docs" / "RHP_QA_REPORT.md").read_text(encoding="utf-8")
    tracker = (ROOT / "docs" / "REDACTION_TRACKER.md").read_text(encoding="utf-8")
    counts = summary["entities_by_type"]
    for pii_type, label in ASSIGNMENT_PII_TYPES:
        row = f"| {label} | {counts.get(pii_type.value, 0)} |"
        assert row in qa
        assert row in tracker
    assert "## Additional detected types" in qa
    for extra_type in ("CIN", "QR_CODE"):
        assert f"| {extra_type} | {counts[extra_type]} |" in qa
