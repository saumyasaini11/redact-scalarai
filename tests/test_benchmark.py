from pathlib import Path
from uuid import uuid4

from docx import Document

from pii_redactor.benchmark import FIXTURES, REQUIRED_PII_TYPES, run_required_type_benchmark
from pii_redactor.docx_io import DocxPackage, extracted_text
from pii_redactor.ensemble import merge_and_score
from pii_redactor.models import PIIType, PolicyAction
from pii_redactor.policy import apply_entity_policy, records_to_redact
from pii_redactor.pseudonyms import Pseudonymizer, assign_replacements
from pii_redactor.recognizers import detect_all


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


def test_strict_company_policy_replaces_benchmark_company_in_docx():
    company_text = next(text for pii_type, text, _ in FIXTURES if pii_type == PIIType.COMPANY)
    original = next(value for pii_type, _, value in FIXTURES if pii_type == PIIType.COMPANY)
    work = Path(".tmp") / f"company-redact-{uuid4().hex}"
    work.mkdir(parents=True)
    source = work / "company-source.docx"
    output = work / "company-redacted.docx"
    document = Document()
    document.add_paragraph(company_text)
    document.save(source)

    try:
        package = DocxPackage(source)
        records = merge_and_score(detect_all(package.extract_blocks(), "IN", "en_core_web_md"), 0.85, 0.60)
        apply_entity_policy(records, company_scope="redact")
        assign_replacements(records, Pseudonymizer("test-only-seed", "synthetic"))
        company_records = [item for item in records if item.pii_type == PIIType.COMPANY]
        assert company_records
        assert any(item.policy_action == PolicyAction.REDACT for item in company_records)
        assert all(item.replacement_value != original for item in company_records)

        package.apply_records(records_to_redact(records))
        package.save(output)
        assert original not in extracted_text(output)
    finally:
        source.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
        work.rmdir()
