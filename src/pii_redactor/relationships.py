from __future__ import annotations

from collections import defaultdict
from hashlib import sha256

from .models import PIIRecord, PIIType


PERSON_TYPES = {
    PIIType.PERSON, PIIType.EMAIL, PIIType.PHONE, PIIType.ADDRESS,
    PIIType.DOB, PIIType.PAN, PIIType.AADHAAR, PIIType.PASSPORT,
}
ORG_TYPES = {
    PIIType.COMPANY, PIIType.EMAIL, PIIType.PHONE, PIIType.ADDRESS,
    PIIType.CIN, PIIType.GSTIN, PIIType.IFSC,
}


def assign_identity_ids(records: list[PIIRecord]) -> None:
    blocks: dict[str, list[PIIRecord]] = defaultdict(list)
    for record in records:
        blocks[record.block_id].append(record)
    for block_id, items in blocks.items():
        person_anchors = [item for item in items if item.pii_type == PIIType.PERSON]
        company_anchors = [item for item in items if item.pii_type == PIIType.COMPANY]
        for person_anchor in person_anchors:
            person_anchor.identity_id = "person-" + sha256(person_anchor.normalized_text.encode()).hexdigest()[:12]
        for company_anchor in company_anchors:
            company_anchor.identity_id = "org-" + sha256(company_anchor.normalized_text.encode()).hexdigest()[:12]
        if len(person_anchors) == 1:
            identity = person_anchors[0].identity_id
            for item in items:
                if item.pii_type in PERSON_TYPES and item.pii_type != PIIType.PERSON:
                    item.identity_id = identity
        if len(company_anchors) == 1:
            identity = company_anchors[0].identity_id
            for item in items:
                if item.identity_id is None and item.pii_type in ORG_TYPES and item.pii_type != PIIType.COMPANY:
                    item.identity_id = identity
    for record in records:
        if record.identity_id is None:
            prefix = "org" if record.pii_type in {PIIType.COMPANY, PIIType.CIN, PIIType.GSTIN, PIIType.IFSC} else "entity"
            record.identity_id = f"{prefix}-" + sha256(
                f"{record.pii_type.value}|{record.normalized_text}".encode()
            ).hexdigest()[:12]
