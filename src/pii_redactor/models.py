from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class PIIType(str, Enum):
    PERSON = "PERSON"
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    COMPANY = "COMPANY"
    ADDRESS = "ADDRESS"
    SSN = "SSN"
    CREDIT_CARD = "CREDIT_CARD"
    DOB = "DOB"
    IPV4 = "IPV4"
    PAN = "PAN"
    AADHAAR = "AADHAAR"
    PASSPORT = "PASSPORT"
    GSTIN = "GSTIN"
    CIN = "CIN"
    IFSC = "IFSC"
    PIN_CODE = "PIN_CODE"
    BIOMETRIC = "BIOMETRIC"
    QR_CODE = "QR_CODE"


class DetectionSource(str, Enum):
    REGEX = "REGEX"
    PRESIDIO_PATTERN = "PRESIDIO_PATTERN"
    SPACY_NER = "SPACY_NER"
    CONTEXT_RULE = "CONTEXT_RULE"
    GAZETTEER = "GAZETTEER"
    CHECKSUM_VALIDATOR = "CHECKSUM_VALIDATOR"
    OCR = "OCR"
    QR_DETECTOR = "QR_DETECTOR"
    HUMAN_REVIEW = "HUMAN_REVIEW"


class ReviewStatus(str, Enum):
    AUTO_APPROVED = "AUTO_APPROVED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    APPROVED = "APPROVED"
    REJECTED_AS_NON_PII = "REJECTED_AS_NON_PII"


class PolicyAction(str, Enum):
    REDACT = "REDACT"
    PROTECT = "PROTECT"
    REVIEW = "REVIEW"
    IGNORE = "IGNORE"


@dataclass(frozen=True)
class Evidence:
    source: DetectionSource
    recognizer_name: str
    score: float
    reason: str
    matched_context: tuple[str, ...] = ()
    validator_results: tuple[str, ...] = ()


@dataclass
class TextBlock:
    block_id: str
    part_name: str
    text: str
    paragraph_index: int
    table_context: str = ""


@dataclass
class PIIRecord:
    record_id: str
    pii_type: PIIType
    original_text: str
    normalized_text: str
    source_kind: str
    document_part: str
    block_id: str
    start_offset: int
    end_offset: int
    evidence: list[Evidence] = field(default_factory=list)
    final_confidence: float = 0.0
    review_status: ReviewStatus = ReviewStatus.NEEDS_REVIEW
    identity_id: str | None = None
    replacement_value: str | None = None
    media_name: str | None = None
    bounding_box: tuple[int, int, int, int] | None = None
    policy_action: PolicyAction = PolicyAction.REVIEW
    policy_reason: str = "Awaiting policy classification"
    policy_locked: bool = False

    def private_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pii_type"] = self.pii_type.value
        data["review_status"] = self.review_status.value
        data["policy_action"] = self.policy_action.value
        for item in data["evidence"]:
            item["source"] = item["source"].value if hasattr(item["source"], "value") else item["source"]
        return data

    def sanitized_dict(self, fingerprint: str) -> dict[str, Any]:
        data = self.private_dict()
        data.pop("original_text", None)
        data.pop("normalized_text", None)
        data["original_fingerprint"] = fingerprint
        return data


@dataclass(frozen=True)
class ReviewDecision:
    record_id: str
    source_hash: str
    action: str
    new_type: str | None = None
    identity_id: str | None = None
    new_start_offset: int | None = None
    new_end_offset: int | None = None
    note: str = ""
