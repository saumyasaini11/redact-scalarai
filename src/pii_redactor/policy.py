from __future__ import annotations

from .models import PIIRecord, PIIType, PolicyAction, ReviewStatus


CORPORATE_FACT_TYPES = {PIIType.COMPANY, PIIType.CIN, PIIType.GSTIN, PIIType.IFSC}


def apply_entity_policy(records: list[PIIRecord], company_scope: str = "protect") -> None:
    """Separate detection confidence from the release-time redaction decision."""
    scope = company_scope.casefold().strip()
    if scope not in {"protect", "review", "redact"}:
        raise ValueError("company_scope must be protect, review, or redact")

    for record in records:
        if record.policy_locked:
            continue
        if record.review_status == ReviewStatus.REJECTED_AS_NON_PII:
            record.policy_action = PolicyAction.IGNORE
            record.policy_reason = "Rejected as non-PII during review"
            continue
        if record.pii_type in CORPORATE_FACT_TYPES:
            if scope == "protect":
                record.policy_action = PolicyAction.PROTECT
                record.policy_reason = "Corporate facts are detected but preserved for document integrity"
                continue
            if scope == "review":
                record.policy_action = PolicyAction.REVIEW
                record.policy_reason = "Corporate entity requires an explicit release decision"
                continue
        if record.review_status in {ReviewStatus.NEEDS_REVIEW, ReviewStatus.LOW_CONFIDENCE}:
            record.policy_action = PolicyAction.REVIEW
            record.policy_reason = "Detection confidence requires human review"
        else:
            record.policy_action = PolicyAction.REDACT
            record.policy_reason = "Approved PII under the active redaction policy"


def records_to_redact(records: list[PIIRecord]) -> list[PIIRecord]:
    return [item for item in records if item.policy_action == PolicyAction.REDACT]


def selected_media_replacements(records: list[PIIRecord], replacements: dict[str, bytes]) -> dict[str, bytes]:
    clear_names = {
        item.media_name for item in records
        if item.media_name and item.policy_locked and item.policy_action == PolicyAction.IGNORE
    }
    redact_names = {
        item.media_name for item in records
        if item.media_name and item.policy_action == PolicyAction.REDACT
    }
    return {
        name: payload for name, payload in replacements.items()
        if name not in clear_names and name in redact_names
    }
