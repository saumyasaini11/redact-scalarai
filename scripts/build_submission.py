"""Build a shareable submission ZIP without source documents or private PII."""

from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

from build_evaluation_report import build_report
from render_evaluation_docx import OUTPUT as EVALUATION_DOCX, build_docx, docx_current
from render_markdown_pdfs import SOURCES, _pdf_path, build_pdfs, pdfs_current


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DOCX = ROOT / "data" / "output" / "Red Herring Prospectus - Pseudonymized.docx"
ARCHIVE = ROOT / "dist" / "scalarai-pii-redaction-submission.zip"
EVALUATION_MD = ROOT / "docs" / "EVALUATION_REPORT.md"
SUMMARY = ROOT / "reports" / "summary_report.json"
SOURCE_DOCX = ROOT / "data" / "input" / "Red Herring Prospectus (1).docx"
SANITIZED_LOG = ROOT / "reports" / "pii_detection_log.sanitized.jsonl"
MEDIA_AUDIT = ROOT / "reports" / "media_audit.json"


def validate_release() -> dict:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    if not SOURCE_DOCX.exists() or not SANITIZED_LOG.exists():
        raise FileNotFoundError("Source DOCX and sanitized detection log are required to validate media")
    actual_output_hash = sha256(OUTPUT_DOCX.read_bytes()).hexdigest()
    if summary["output_sha256"] != actual_output_hash:
        raise ValueError("Final DOCX hash does not match summary_report.json")
    if summary["source_sha256"] != sha256(SOURCE_DOCX.read_bytes()).hexdigest():
        raise ValueError("Source DOCX hash does not match summary_report.json")
    if not summary["release_ready"] or summary["qa_errors"] or summary["unresolved_review_items"]:
        raise ValueError("Final DOCX has not passed the release gate")
    if sum(summary["entities_by_policy"].values()) != summary["total_candidates"]:
        raise ValueError("Policy counts do not equal total candidates")
    for path in (ROOT / "README.md", ROOT / "docs" / "REDACTION_TRACKER.md",
                 ROOT / "docs" / "RHP_QA_REPORT.md", EVALUATION_MD):
        content = path.read_text(encoding="utf-8")
        if summary["source_sha256"] not in content or actual_output_hash not in content:
            raise ValueError(f"Release hashes are missing or stale in {path.relative_to(ROOT)}")

    with ZipFile(SOURCE_DOCX) as source, ZipFile(OUTPUT_DOCX) as output:
        source_media = {name: sha256(source.read(name)).hexdigest()
                        for name in source.namelist() if name.startswith("word/media/")}
        output_media = {name: sha256(output.read(name)).hexdigest()
                        for name in output.namelist() if name.startswith("word/media/")}
    changed_media = {name for name, digest in source_media.items() if output_media.get(name) != digest}
    if len(changed_media) != summary["media_replaced"] or len(source_media) != summary["media_total"]:
        raise ValueError("Media counts do not match the final DOCX")
    audit = [json.loads(line) for line in SANITIZED_LOG.read_text(encoding="utf-8").splitlines()
             if line.strip()]
    if any(row.get("media_name") in source_media and row["media_name"] not in changed_media
           for row in audit if row.get("media_name") and row.get("policy_action") == "REDACT"):
        raise ValueError("Audit log says REDACT for media preserved in the final DOCX")
    media_candidates: dict[str, list[dict]] = {name: [] for name in source_media}
    for row in audit:
        name = row.get("media_name")
        if name in media_candidates:
            media_candidates[name].append({
                "pii_type": row["pii_type"],
                "policy_action": row["policy_action"],
                "policy_reason": row["policy_reason"],
            })
    return {
        "source_sha256": summary["source_sha256"],
        "output_sha256": actual_output_hash,
        "media_total": len(source_media),
        "media_replaced": len(changed_media),
        "assets": [
            {"media_name": name, "replaced": name in changed_media,
             "candidates": media_candidates[name]}
            for name in sorted(source_media)
        ],
    }


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [ROOT / line for line in result.stdout.splitlines() if line.strip()]
    return [
        path for path in paths
        if path.is_file()
        and ".venv" not in path.parts
        and "data/private" not in path.as_posix()
        and "data/input" not in path.as_posix()
    ]


def main() -> int:
    if not OUTPUT_DOCX.exists():
        raise FileNotFoundError("Run the final redaction pipeline before building the submission")
    build_report()
    media_audit = validate_release()
    MEDIA_AUDIT.write_text(json.dumps(media_audit, indent=2) + "\n", encoding="utf-8")
    if not docx_current():
        build_docx()
    if not pdfs_current():
        try:
            build_pdfs()
        except ImportError as exc:
            raise RuntimeError(
                "PDF build dependencies are missing. Install requirements-pdf.txt, then rebuild."
            ) from exc
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(ARCHIVE, "w", ZIP_DEFLATED) as archive:
        for path in repository_files():
            if path.resolve() in {EVALUATION_MD.resolve(), EVALUATION_DOCX.resolve()}:
                continue
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.write(OUTPUT_DOCX, f"deliverables/{OUTPUT_DOCX.name}")
        for source in SOURCES:
            if source != EVALUATION_MD:
                archive.write(_pdf_path(source), f"readable/{_pdf_path(source).name}")
        archive.write(EVALUATION_MD, EVALUATION_MD.relative_to(ROOT).as_posix())
        archive.write(EVALUATION_DOCX, EVALUATION_DOCX.relative_to(ROOT).as_posix())
        archive.write(_pdf_path(EVALUATION_MD), "readable/EVALUATION_REPORT.pdf")
    print(f"Created {ARCHIVE} ({ARCHIVE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
