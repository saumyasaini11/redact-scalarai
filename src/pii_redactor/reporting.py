from __future__ import annotations

from collections import Counter
from hashlib import sha256
import hmac
import json
from pathlib import Path

from .models import ASSIGNMENT_PII_TYPES, DetectionSource, PIIRecord, PolicyAction, ReviewStatus


def _fingerprint(secret: str, record: PIIRecord) -> str:
    return hmac.new(
        secret.encode("utf-8"),
        f"{record.pii_type.value}|{record.normalized_text}".encode("utf-8"),
        sha256,
    ).hexdigest()[:20]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_audit_logs(private_path: Path, sanitized_path: Path, records: list[PIIRecord], secret: str) -> None:
    write_jsonl(private_path, [record.private_dict() for record in records])
    write_jsonl(
        sanitized_path,
        [record.sanitized_dict(_fingerprint(secret, record)) for record in records],
    )


def build_summary(records: list[PIIRecord], source_hash: str, output_hash: str | None,
                  seed_fingerprint: str, media_inventory: list[dict], output_path: str | None) -> dict:
    type_counts = Counter(record.pii_type.value for record in records)
    status_counts = Counter(record.review_status.value for record in records)
    policy_counts = Counter(record.policy_action.value for record in records)
    source_counts = Counter(
        item.source.value for record in records for item in record.evidence
    )
    human_reviewed = sum(
        any(evidence.source == DetectionSource.HUMAN_REVIEW for evidence in record.evidence)
        for record in records
    )
    policy_finalized = sum(
        any(evidence.source == DetectionSource.POLICY for evidence in record.evidence)
        for record in records
    )
    return {
        "source_sha256": source_hash,
        "output_sha256": output_hash,
        "output_path": output_path,
        "seed_fingerprint": seed_fingerprint,
        "total_candidates": len(records),
        "entities_by_type": dict(sorted(type_counts.items())),
        "entities_by_status": dict(sorted(status_counts.items())),
        "entities_by_policy": dict(sorted(policy_counts.items())),
        "evidence_by_source": dict(sorted(source_counts.items())),
        "automatically_replaced": sum(
            item.review_status == ReviewStatus.AUTO_APPROVED and item.policy_action == PolicyAction.REDACT
            for item in records
        ),
        "redacted_entities": policy_counts.get(PolicyAction.REDACT.value, 0),
        "protected_entities": policy_counts.get(PolicyAction.PROTECT.value, 0),
        "ignored_entities": policy_counts.get(PolicyAction.IGNORE.value, 0),
        "policy_review_required": policy_counts.get(PolicyAction.REVIEW.value, 0),
        "review_approved": human_reviewed,
        "policy_finalized": policy_finalized,
        "review_rejected": status_counts.get(ReviewStatus.REJECTED_AS_NON_PII.value, 0),
        "manual_review_required": policy_counts.get(PolicyAction.REVIEW.value, 0),
        "confidence_review_flags": status_counts.get(ReviewStatus.NEEDS_REVIEW.value, 0),
        "low_confidence_inspection": status_counts.get(ReviewStatus.LOW_CONFIDENCE.value, 0),
        "media_total": len(media_inventory),
        "media_replaced": sum(bool(item.get("replaced")) for item in media_inventory),
        "release_ready": policy_counts.get(PolicyAction.REVIEW.value, 0) == 0,
    }


def write_summary(path: Path, summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_tracker(path: Path, summary: dict) -> None:
    lines = [
        "# PII Redaction Tracker",
        "",
        f"- Source SHA-256: `{summary['source_sha256']}`",
        f"- Output SHA-256: `{summary.get('output_sha256') or 'TBD'}`",
        f"- Release ready: `{summary['release_ready']}`",
        f"- Total candidates reviewed: `{summary['total_candidates']}`",
        f"- Automatically replaced: `{summary['automatically_replaced']}`",
        f"- Redacted by policy: `{summary.get('redacted_entities', 0)}`",
        f"- Protected by policy: `{summary.get('protected_entities', 0)}`",
        f"- Ignored by policy: `{summary.get('ignored_entities', 0)}`",
        f"- Approved during review: `{summary.get('review_approved', 0)}`",
        f"- Finalized by explicit privacy-first policy: `{summary.get('policy_finalized', 0)}`",
        f"- Rejected as non-PII: `{summary.get('review_rejected', 0)}`",
        f"- Manual review required: `{summary['manual_review_required']}`",
        f"- Confidence flags resolved by policy: `{summary.get('confidence_review_flags', 0)}`",
        f"- Low-confidence inspection: `{summary['low_confidence_inspection']}`",
        f"- Media replaced: `{summary['media_replaced']}/{summary['media_total']}`",
        f"- Text blocks preserved: `{summary.get('output_text_blocks', 'TBD')}/{summary.get('source_text_blocks', 'TBD')}`",
        f"- DOCX structure signature preserved: `{summary.get('structure_preserved', 'TBD')}`",
        "",
        "## Assignment-required PII types",
        "",
        "Counts are detected candidates in this document. Zero means none were detected, not proof of absence.",
        "",
        "| Type | Count |",
        "|---|---:|",
    ]
    counts = summary["entities_by_type"]
    required_codes = {pii_type.value for pii_type, _ in ASSIGNMENT_PII_TYPES}
    lines.extend(f"| {label} | {counts.get(pii_type.value, 0)} |" for pii_type, label in ASSIGNMENT_PII_TYPES)
    additional = [(key, value) for key, value in counts.items() if key not in required_codes]
    if additional:
        lines.extend(["", "## Additional detected types", "", "| Type | Count |", "|---|---:|"])
        lines.extend(f"| {key} | {value} |" for key, value in additional)
    lines.extend(["", "## Policy decisions", "", "| Action | Count |", "|---|---:|"])
    lines.extend(f"| {key} | {value} |" for key, value in summary.get("entities_by_policy", {}).items())
    lines.extend(["", "## Evidence by source", "", "| Source | Contributions |", "|---|---:|"])
    lines.extend(f"| {key} | {value} |" for key, value in summary["evidence_by_source"].items())
    lines.extend([
        "",
        "Raw originals and mappings are intentionally excluded from this tracker.",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
