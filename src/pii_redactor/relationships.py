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
        person_anchor = next((item for item in items if item.pii_type == PIIType.PERSON), None)
        company_anchor = next((item for item in items if item.pii_type == PIIType.COMPANY), None)
        if person_anchor:
            identity = "person-" + sha256(person_anchor.normalized_text.encode()).hexdigest()[:12]
            for item in items:
                if item.pii_type in PERSON_TYPES:
                    item.identity_id = identity
        if company_anchor:
            identity = "org-" + sha256(company_anchor.normalized_text.encode()).hexdigest()[:12]
            for item in items:
                if item.identity_id is None and item.pii_type in ORG_TYPES:
                    item.identity_id = identity
    for record in records:
        if record.identity_id is None:
            prefix = "org" if record.pii_type in {PIIType.COMPANY, PIIType.CIN, PIIType.GSTIN, PIIType.IFSC} else "entity"
            record.identity_id = f"{prefix}-" + sha256(
                f"{record.pii_type.value}|{record.normalized_text}".encode()
            ).hexdigest()[:12]

