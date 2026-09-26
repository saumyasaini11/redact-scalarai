from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZIP_DEFLATED, ZipFile

from .config import Settings
from .models import ReviewDecision


SAFE_STEM = re.compile(r"[^A-Za-z0-9._-]+")
MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_UNCOMPRESSED_BYTES = 300 * 1024 * 1024
MAX_PACKAGE_PARTS = 5000


@dataclass(frozen=True)
class AppRun:
    run_id: str
    root: Path
    settings: Settings


def validate_docx_upload(payload: bytes) -> None:
    if len(payload) > MAX_UPLOAD_BYTES:
        raise ValueError("DOCX exceeds the 100 MB upload limit")
    try:
        with ZipFile(BytesIO(payload)) as archive:
            members = archive.infolist()
            names = {item.filename for item in members}
            if len(members) > MAX_PACKAGE_PARTS:
                raise ValueError("DOCX contains too many package parts")
            if {"[Content_Types].xml", "word/document.xml"} - names:
                raise ValueError("The uploaded ZIP is not a valid Word document")
            if sum(item.file_size for item in members) > MAX_UNCOMPRESSED_BYTES:
                raise ValueError("DOCX expands beyond the 300 MB safety limit")
            if any(item.flag_bits & 0x1 for item in members):
                raise ValueError("Encrypted DOCX packages are not supported")
            if any(".." in Path(item.filename).parts or item.filename.startswith(("/", "\\")) for item in members):
                raise ValueError("DOCX contains an unsafe package path")
    except BadZipFile as exc:
        raise ValueError("The uploaded file is not a valid DOCX package") from exc


def create_app_run(
    project_root: Path,
    filename: str,
    payload: bytes,
    *,
    seed: str,
    mode: str,
    high_threshold: float,
    medium_threshold: float,
    default_region: str,
    replace_all_media: bool,
    company_scope: str = "protect",
    auto_redact_pending: bool = False,
    spacy_model: str = "en_core_web_md",
    tesseract_cmd: str = "",
) -> AppRun:
    """Create an isolated, deterministic workspace for one uploaded DOCX."""
    validate_docx_upload(payload)
    policy = json.dumps({
        "mode": mode,
        "high": high_threshold,
        "medium": medium_threshold,
        "region": default_region,
        "replace_all_media": replace_all_media,
        "company_scope": company_scope,
        "auto_redact_pending": auto_redact_pending,
        "seed_fingerprint": sha256(seed.encode("utf-8")).hexdigest()[:16],
    }, sort_keys=True).encode("utf-8")
    run_id = sha256(payload + policy).hexdigest()[:16]
    root = (project_root / "data" / "app_runs" / run_id).resolve()
    private_dir = root / "private"
    reports_dir = root / "reports"
    output_dir = root / "output"
    for directory in (private_dir, reports_dir, output_dir):
        directory.mkdir(parents=True, exist_ok=True)
    safe_name = SAFE_STEM.sub("_", Path(filename).name).strip("._") or "uploaded.docx"
    if not safe_name.casefold().endswith(".docx"):
        safe_name += ".docx"
    input_path = root / safe_name
    input_path.write_bytes(payload)
    settings = Settings(
        project_root=root,
        input_path=input_path,
        final_output_path=output_dir / f"{Path(safe_name).stem} - Pseudonymized.docx",
        draft_output_path=output_dir / f"{Path(safe_name).stem} - Review Draft.docx",
        private_dir=private_dir,
        reports_dir=reports_dir,
        mode=mode,
        high_threshold=high_threshold,
        medium_threshold=medium_threshold,
        default_region=default_region,
        company_scope=company_scope,
        replace_all_media=replace_all_media,
        strict_release=True,
        spacy_model=spacy_model,
        tesseract_cmd=tesseract_cmd,
        seed_env="PII_REDACTION_SEED",
        secret_seed=seed,
    )
    return AppRun(run_id=run_id, root=root, settings=settings)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def save_review_decisions(path: Path, rows: list[dict], source_hash: str) -> int:
    """Merge selected UI decisions without discarding decisions saved on another filtered page."""
    existing: dict[str, ReviewDecision] = {}
    if path.exists():
        for row in read_jsonl(path):
            decision = ReviewDecision(**row)
            if decision.source_hash == source_hash:
                existing[decision.record_id] = decision
    saved = 0
    for row in rows:
        action = str(row.get("decision") or "").strip()
        if not action:
            continue
        existing[str(row["record_id"])] = ReviewDecision(
            record_id=str(row["record_id"]),
            source_hash=source_hash,
            action=action,
            new_type=(str(row.get("new_type") or "").strip() or None),
            identity_id=(str(row.get("identity_id") or "").strip() or None),
            note=str(row.get("note") or "").strip(),
        )
        saved += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for decision in sorted(existing.values(), key=lambda item: item.record_id):
            handle.write(json.dumps(decision.__dict__, ensure_ascii=False) + "\n")
    return saved


def finalize_pending_privacy_first(path: Path, queue: list[dict]) -> int:
    """Resolve a queue conservatively without changing legitimate corporate facts.

    Corporate names and identifiers are explicitly protected. Other pending PII is
    redacted. This is a policy action, not a substitute for human annotation and not
    evidence of detector precision.
    """
    if not queue:
        return 0
    source_hashes = {str(item.get("source_hash") or "") for item in queue}
    if len(source_hashes) != 1 or not next(iter(source_hashes)):
        raise ValueError("Review queue has missing or inconsistent source hashes")
    corporate_types = {"COMPANY", "CIN", "GSTIN", "IFSC"}
    rows = []
    for item in queue:
        protect = str(item.get("pii_type")) in corporate_types
        rows.append({
            "record_id": item["record_id"],
            "decision": "PROTECT" if protect else "REDACT",
            "identity_id": item.get("identity_id") or "",
            "note": (
                "Privacy-first finalization: preserve detected corporate fact"
                if protect else "Privacy-first finalization: redact unresolved personal PII"
            ),
        })
    return save_review_decisions(path, rows, next(iter(source_hashes)))


def build_download_bundle(run: AppRun, output_path: Path) -> bytes:
    """Return a shareable ZIP that excludes raw PII, decisions, and identity mappings."""
    buffer = BytesIO()
    candidates = [
        output_path,
        run.settings.reports_dir / "summary_report.json",
        run.settings.reports_dir / "rhp_release_validation.csv",
        run.settings.reports_dir / "pii_detection_log.sanitized.jsonl",
        run.root / "docs" / "RHP_QA_REPORT.md",
        run.root / "docs" / "REDACTION_TRACKER.md",
    ]
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for path in candidates:
            if path.exists():
                archive.write(path, arcname=path.name)
    return buffer.getvalue()
