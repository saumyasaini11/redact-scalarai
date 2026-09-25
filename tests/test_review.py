from pii_redactor.models import PIIRecord, PIIType, ReviewDecision, ReviewStatus
from pii_redactor.review import apply_decisions


def test_adjust_span_refreshes_original_text():
    record = PIIRecord(
        record_id="r1", pii_type=PIIType.PERSON,
        original_text="Name", normalized_text="name", source_kind="native_text",
        document_part="word/document.xml", block_id="b1", start_offset=0, end_offset=4,
    )
    decision = ReviewDecision(
        record_id="r1", source_hash="hash", action="ADJUST_SPAN",
        new_start_offset=5, new_end_offset=15,
    )
    apply_decisions([record], {"r1": decision}, {"b1": "Name John Smith"})
    assert record.original_text == "John Smith"
    assert record.review_status == ReviewStatus.APPROVED
