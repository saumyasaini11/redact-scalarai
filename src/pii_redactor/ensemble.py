from __future__ import annotations

from collections import defaultdict

from .models import PIIRecord, PIIType, PolicyAction, ReviewStatus


TYPE_PRIORITY = {
    PIIType.PAN: 100,
    PIIType.AADHAAR: 100,
    PIIType.PASSPORT: 100,
    PIIType.SSN: 100,
    PIIType.CREDIT_CARD: 100,
    PIIType.EMAIL: 95,
    PIIType.PHONE: 95,
    PIIType.IPV4: 95,
    PIIType.GSTIN: 90,
    PIIType.CIN: 90,
    PIIType.IFSC: 90,
    PIIType.DOB: 90,
    PIIType.ADDRESS: 80,
    PIIType.PERSON: 70,
    PIIType.COMPANY: 60,
    PIIType.PIN_CODE: 20,
    PIIType.BIOMETRIC: 100,
    PIIType.QR_CODE: 100,
}


def merge_and_score(records: list[PIIRecord], high_threshold: float,
                    medium_threshold: float) -> list[PIIRecord]:
    merged: dict[tuple, PIIRecord] = {}
    for record in records:
        key = (
            record.source_kind,
            record.block_id,
            record.start_offset,
            record.end_offset,
            record.pii_type,
            record.media_name,
        )
        existing = merged.get(key)
        if existing is None:
            merged[key] = record
        else:
            existing.evidence.extend(record.evidence)

    scored: list[PIIRecord] = []
    for record in merged.values():
        base = max((item.score for item in record.evidence), default=0.0)
        independent = len({item.source for item in record.evidence})
        corroboration = max(0, independent - 1) * 0.08
        record.final_confidence = min(0.99, base + corroboration)
        if record.policy_locked and record.policy_action == PolicyAction.IGNORE:
            record.review_status = ReviewStatus.REJECTED_AS_NON_PII
        elif record.final_confidence >= high_threshold:
            record.review_status = ReviewStatus.AUTO_APPROVED
        elif record.final_confidence >= medium_threshold:
            record.review_status = ReviewStatus.NEEDS_REVIEW
        else:
            record.review_status = ReviewStatus.LOW_CONFIDENCE
        scored.append(record)

    by_block: dict[tuple[str, str], list[PIIRecord]] = defaultdict(list)
    media: list[PIIRecord] = []
    for record in scored:
        if record.source_kind == "native_text":
            by_block[(record.document_part, record.block_id)].append(record)
        else:
            media.append(record)

    resolved: list[PIIRecord] = []
    for items in by_block.values():
        selected: list[PIIRecord] = []
        ranked = sorted(
            items,
            key=lambda item: (
                item.final_confidence,
                TYPE_PRIORITY.get(item.pii_type, 0),
                item.end_offset - item.start_offset,
                -item.start_offset,
            ),
            reverse=True,
        )
        for candidate in ranked:
            conflicts = [
                item for item in selected
                if candidate.start_offset < item.end_offset and candidate.end_offset > item.start_offset
            ]
            if not conflicts:
                selected.append(candidate)
                continue
            # A strongly supported address replaces a nested lower-level entity as one safe span.
            if candidate.pii_type == PIIType.ADDRESS and candidate.final_confidence >= 0.85 and all(
                candidate.start_offset <= item.start_offset and candidate.end_offset >= item.end_offset
                for item in conflicts
            ):
                selected = [item for item in selected if item not in conflicts]
                selected.append(candidate)
        resolved.extend(sorted(selected, key=lambda item: item.start_offset))
    resolved.extend(media)
    return sorted(
        resolved,
        key=lambda item: (item.document_part, item.block_id, item.start_offset, item.pii_type.value),
    )
