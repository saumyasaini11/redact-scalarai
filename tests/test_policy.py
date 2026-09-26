from pii_redactor.models import PIIRecord, PIIType, PolicyAction, ReviewStatus
from pii_redactor.policy import apply_entity_policy


def _record(pii_type: PIIType, status: ReviewStatus = ReviewStatus.AUTO_APPROVED) -> PIIRecord:
    return PIIRecord(
        record_id=pii_type.value,
        pii_type=pii_type,
        original_text="KSH International Limited" if pii_type == PIIType.COMPANY else "Sarthak Malvadkar",
        normalized_text="value",
        source_kind="native_text",
        document_part="word/document.xml",
        block_id="b",
        start_offset=0,
        end_offset=10,
        review_status=status,
    )


def test_company_detection_is_protected_while_person_is_redacted():
    company = _record(PIIType.COMPANY)
    person = _record(PIIType.PERSON)
    apply_entity_policy([company, person], "protect")
    assert company.policy_action == PolicyAction.PROTECT
    assert "preserved" in company.policy_reason
    assert person.policy_action == PolicyAction.REDACT


def test_pending_person_requires_review():
    person = _record(PIIType.PERSON, ReviewStatus.NEEDS_REVIEW)
    apply_entity_policy([person], "protect")
    assert person.policy_action == PolicyAction.REVIEW
