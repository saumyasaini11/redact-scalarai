from pathlib import Path
from uuid import uuid4

from docx import Document

from pii_redactor.app_service import (
    build_download_bundle,
    create_app_run,
    finalize_pending_privacy_first,
    save_review_decisions,
)


def _docx_bytes(path: Path) -> bytes:
    document = Document()
    document.add_paragraph("Email: test@example.test")
    document.save(path)
    return path.read_bytes()


def _workdir() -> Path:
    path = Path(".tmp") / f"test-{uuid4().hex}"
    path.mkdir(parents=True)
    return path


def test_app_run_is_isolated_and_bundle_excludes_private_files():
    tmp_path = _workdir()
    payload = _docx_bytes(tmp_path / "input.docx")
    run = create_app_run(
        tmp_path, "../unsafe name.docx", payload, seed="secret", mode="mask",
        high_threshold=0.85, medium_threshold=0.60, default_region="IN",
        replace_all_media=True,
    )
    assert run.settings.input_path.parent == run.root
    assert run.settings.secret_seed == "secret"

    output = run.settings.final_output_path
    output.write_bytes(payload)
    (run.settings.private_dir / "raw.jsonl").write_text("secret", encoding="utf-8")
    bundle = build_download_bundle(run, output)
    assert b"raw.jsonl" not in bundle


def test_review_decisions_only_write_decided_rows():
    tmp_path = _workdir()
    count = save_review_decisions(tmp_path / "decisions.jsonl", [
        {"record_id": "1", "decision": "APPROVE"},
        {"record_id": "2", "decision": ""},
    ], "source")
    assert count == 1
    assert '"record_id": "1"' in (tmp_path / "decisions.jsonl").read_text(encoding="utf-8")


def test_privacy_first_finalization_protects_corporate_facts():
    tmp_path = _workdir()
    path = tmp_path / "decisions.jsonl"
    queue = [
        {"record_id": "1", "source_hash": "source", "identity_id": "person-1", "pii_type": "PERSON"},
        {"record_id": "2", "source_hash": "source", "identity_id": "org-1", "pii_type": "COMPANY"},
    ]

    assert finalize_pending_privacy_first(path, queue) == 2
    contents = path.read_text(encoding="utf-8")
    assert contents.count('"action": "REDACT"') == 1
    assert contents.count('"action": "PROTECT"') == 1
