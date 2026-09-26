from __future__ import annotations

import json
from pathlib import Path

from .models import DetectionSource, Evidence, PIIRecord, PolicyAction, ReviewDecision, ReviewStatus


VALID_ACTIONS = {
    "APPROVE", "REJECT_AS_NON_PII", "RETYPE", "ADJUST_SPAN",
    "LINK_IDENTITY", "UNLINK_IDENTITY", "FORCE_MEDIA_REPLACEMENT", "CLEAR_MEDIA",
    "REDACT", "PROTECT", "IGNORE",
}


def load_decisions(path: Path, source_hash: str) -> dict[str, ReviewDecision]:
    if not path.exists():
        return {}
    decisions: dict[str, ReviewDecision] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        decision = ReviewDecision(**raw)
        if decision.source_hash != source_hash:
            raise RuntimeError("Review decision source hash does not match the current dataset")
        if decision.action not in VALID_ACTIONS:
            raise ValueError(f"Unsupported review action: {decision.action}")
        decisions[decision.record_id] = decision
    return decisions


def apply_decisions(
    records: list[PIIRecord],
    decisions: dict[str, ReviewDecision],
    block_text: dict[str, str] | None = None,
) -> None:
    for record in records:
        decision = decisions.get(record.record_id)
        if not decision:
            continue
        policy_finalization = decision.note.startswith("Privacy-first finalization:")
        record.evidence.append(Evidence(
            DetectionSource.POLICY if policy_finalization else DetectionSource.HUMAN_REVIEW,
            f"{'policy' if policy_finalization else 'human'}_{decision.action.casefold()}",
            1.0,
            decision.note or f"Human review decision: {decision.action}",
        ))
        if decision.action == "APPROVE":
            record.review_status = ReviewStatus.APPROVED
        elif decision.action == "REDACT":
            record.review_status = ReviewStatus.APPROVED
            record.policy_action = PolicyAction.REDACT
            record.policy_reason = decision.note or "Explicit human redaction decision"
            record.policy_locked = True
        elif decision.action == "PROTECT":
            record.review_status = ReviewStatus.APPROVED
            record.policy_action = PolicyAction.PROTECT
            record.policy_reason = decision.note or "Explicit human protection decision"
            record.policy_locked = True
        elif decision.action == "IGNORE":
            record.review_status = ReviewStatus.REJECTED_AS_NON_PII
            record.policy_action = PolicyAction.IGNORE
            record.policy_reason = "Explicit human ignore decision"
            record.policy_locked = True
        elif decision.action == "REJECT_AS_NON_PII":
            record.review_status = ReviewStatus.REJECTED_AS_NON_PII
        elif decision.action == "RETYPE" and decision.new_type:
            record.pii_type = type(record.pii_type)(decision.new_type)
            record.review_status = ReviewStatus.APPROVED
        elif decision.action == "ADJUST_SPAN":
            if decision.new_start_offset is None or decision.new_end_offset is None:
                raise ValueError("ADJUST_SPAN requires new_start_offset and new_end_offset")
            if not 0 <= decision.new_start_offset < decision.new_end_offset:
                raise ValueError("ADJUST_SPAN offsets are invalid")
            text = (block_text or {}).get(record.block_id)
            if text is not None:
                if decision.new_end_offset > len(text):
                    raise ValueError("ADJUST_SPAN end offset exceeds the source block")
                record.original_text = text[decision.new_start_offset:decision.new_end_offset]
                record.normalized_text = " ".join(record.original_text.casefold().split())
            record.start_offset = decision.new_start_offset
            record.end_offset = decision.new_end_offset
            record.review_status = ReviewStatus.APPROVED
        elif decision.action == "LINK_IDENTITY" and decision.identity_id:
            record.identity_id = decision.identity_id
            record.review_status = ReviewStatus.APPROVED
        elif decision.action == "UNLINK_IDENTITY":
            record.identity_id = None
            record.review_status = ReviewStatus.APPROVED
        elif decision.action == "FORCE_MEDIA_REPLACEMENT":
            record.review_status = ReviewStatus.APPROVED
            record.policy_action = PolicyAction.REDACT
            record.policy_reason = "Explicit media replacement decision"
            record.policy_locked = True
        elif decision.action == "CLEAR_MEDIA":
            record.review_status = ReviewStatus.APPROVED
            record.policy_action = PolicyAction.IGNORE
            record.policy_reason = "Explicit decision to retain this media asset"
            record.policy_locked = True


def unresolved(records: list[PIIRecord]) -> list[PIIRecord]:
    return [
        item for item in records
        if item.policy_action == PolicyAction.REVIEW
    ]


def approved(records: list[PIIRecord]) -> list[PIIRecord]:
    return [
        item for item in records
        if item.review_status in {ReviewStatus.AUTO_APPROVED, ReviewStatus.APPROVED}
    ]


def write_queue(path: Path, records: list[PIIRecord], source_hash: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in unresolved(records):
            payload = record.private_dict()
            payload["source_hash"] = source_hash
            payload["allowed_actions"] = sorted(VALID_ACTIONS)
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
