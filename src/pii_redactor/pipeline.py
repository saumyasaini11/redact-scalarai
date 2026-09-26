from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from .config import Settings
from .docx_io import DocxPackage
from .ensemble import merge_and_score
from .evaluation import evaluate, write_evaluation
from .media import analyze_media
from .models import PIIRecord
from .policy import apply_entity_policy, records_to_redact, selected_media_replacements
from .pseudonyms import Pseudonymizer, assign_replacements
from .qa import (
    file_sha256,
    media_hashes,
    replacement_application_failures,
    scan_original_values,
    structure_signature,
    validate_structure_preservation,
    validate_docx,
)
from .recognizers import detect_all
from .relationships import assign_identity_ids
from .reporting import build_summary, write_audit_logs, write_summary, write_tracker
from .review import apply_decisions, load_decisions, unresolved, write_queue


@dataclass(frozen=True)
class PipelineResult:
    output_path: Path
    release_ready: bool
    unresolved_count: int
    record_count: int
    qa_errors: tuple[str, ...]


def _write_annotation_manifest(path: Path, source_hash: str, blocks) -> None:
    if path.exists() and path.stat().st_size:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for block in blocks:
            handle.write(json.dumps({
                "source_hash": source_hash,
                "document_part": block.part_name,
                "block_id": block.block_id,
                "text": block.text,
                "annotations": [],
                "review_status": "UNREVIEWED",
            }, ensure_ascii=False) + "\n")


def run_pipeline(settings: Settings) -> PipelineResult:
    settings.private_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.final_output_path.parent.mkdir(parents=True, exist_ok=True)
    (settings.project_root / "docs").mkdir(parents=True, exist_ok=True)

    package = DocxPackage(settings.input_path)
    source_hash = package.source_hash
    blocks = package.extract_blocks()

    _write_annotation_manifest(
        settings.private_dir / "full_dataset_annotation_manifest.private.jsonl",
        source_hash,
        blocks,
    )

    text_records = detect_all(blocks, settings.default_region, settings.spacy_model)
    media_records, media_replacements, media_inventory = analyze_media(
        package.media(), settings.default_region, settings.tesseract_cmd, settings.replace_all_media
    )
    records = merge_and_score(
        text_records + media_records,
        settings.high_threshold,
        settings.medium_threshold,
    )

    decisions_path = settings.private_dir / "review_decisions.jsonl"
    decisions = load_decisions(decisions_path, source_hash)
    apply_decisions(records, decisions, {block.block_id: block.text for block in blocks})
    apply_entity_policy(records, settings.company_scope)
    assign_identity_ids(records)
    pseudonymizer = Pseudonymizer(settings.seed, settings.mode)
    assign_replacements(records, pseudonymizer)

    write_queue(settings.private_dir / "review_queue.jsonl", records, source_hash)
    write_audit_logs(
        settings.private_dir / "pii_detection_log.private.jsonl",
        settings.reports_dir / "pii_detection_log.sanitized.jsonl",
        records,
        settings.seed,
    )
    (settings.private_dir / "entity_mapping.private.jsonl").write_text(
        "".join(
            json.dumps({
                "record_id": item.record_id,
                "pii_type": item.pii_type.value,
                "original": item.original_text,
                "replacement": item.replacement_value,
                "identity_id": item.identity_id,
            }, ensure_ascii=False) + "\n"
            for item in records
        ),
        encoding="utf-8",
    )

    pending = unresolved(records)
    release_ready = not pending
    output_path = settings.final_output_path if release_ready else settings.draft_output_path
    if settings.strict_release and pending:
        output_path = settings.draft_output_path

    patch_records = records_to_redact(records)
    media_replacements = selected_media_replacements(
        records, media_replacements, replace_all=settings.replace_all_media
    )
    for item in media_inventory:
        item["replaced"] = item.get("media_name") in media_replacements
    package.apply_records(patch_records)
    package.replace_media(media_replacements)
    package.scrub_metadata()
    package.save(output_path)

    qa_errors = validate_docx(output_path)
    qa_errors.extend(validate_structure_preservation(settings.input_path, output_path))
    source_media_hashes = {item["media_name"]: item.get("source_sha256") for item in media_inventory}
    output_media = media_hashes(output_path)
    unchanged_media = [name for name in media_replacements if source_media_hashes.get(name) == output_media.get(name)]
    if unchanged_media:
        qa_errors.append(f"Original media remained unchanged: {unchanged_media}")
    application_failures = replacement_application_failures(output_path, patch_records)
    if application_failures:
        qa_errors.append(f"Approved replacements missing from their output blocks: {len(application_failures)}")
    residuals = scan_original_values(output_path, patch_records) if release_ready else []
    if residuals:
        qa_errors.append(f"Residual approved originals found in output XML: {len(residuals)}")

    output_hash = file_sha256(output_path)
    summary = build_summary(
        records, source_hash, output_hash, pseudonymizer.seed_fingerprint,
        media_inventory,
        str(output_path.relative_to(settings.project_root))
        if output_path.is_relative_to(settings.project_root) else output_path.name,
    )
    summary["qa_errors"] = qa_errors
    summary["replacement_application_failures"] = len(application_failures)
    summary["residual_approved_originals_at_release"] = len(residuals) if release_ready else "NOT_RUN_DRAFT"
    summary["unresolved_review_items"] = len(pending)
    summary["source_text_blocks"] = len(blocks)
    summary["output_text_blocks"] = len(DocxPackage(output_path).extract_blocks())
    summary["source_structure"] = structure_signature(settings.input_path)
    summary["output_structure"] = structure_signature(output_path)
    summary["structure_preserved"] = summary["source_structure"] == summary["output_structure"]
    write_summary(settings.reports_dir / "summary_report.json", summary)
    write_tracker(settings.project_root / "docs" / "REDACTION_TRACKER.md", summary)

    evaluation = evaluate(
        records,
        settings.private_dir / "gold_annotations.jsonl",
        settings.private_dir / "full_dataset_annotation_manifest.private.jsonl",
    )
    evaluation["source_sha256"] = source_hash
    evaluation["output_sha256"] = output_hash
    evaluation["media_total"] = len(media_inventory)
    evaluation["media_replaced"] = summary["media_replaced"]
    write_evaluation(
        evaluation,
        settings.project_root / "docs" / "RHP_QA_REPORT.md",
        settings.reports_dir / "rhp_release_validation.csv",
        title="RHP Release QA Report",
    )
    return PipelineResult(
        output_path=output_path,
        release_ready=release_ready and not qa_errors,
        unresolved_count=len(pending),
        record_count=len(records),
        qa_errors=tuple(qa_errors),
    )
