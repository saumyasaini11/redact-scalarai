from pii_redactor.ensemble import merge_and_score
from pii_redactor.models import DetectionSource, Evidence, PIIRecord, PIIType


def record(source: DetectionSource) -> PIIRecord:
    return PIIRecord(
        record_id="x", pii_type=PIIType.EMAIL, original_text="a@example.com",
        normalized_text="a@example.com", source_kind="native_text",
        document_part="word/document.xml", block_id="b", start_offset=0, end_offset=13,
        evidence=[Evidence(source, source.value, 0.80, "test")],
    )


def test_independent_sources_raise_confidence():
    output = merge_and_score([record(DetectionSource.REGEX), record(DetectionSource.CONTEXT_RULE)], 0.85, 0.60)
    assert len(output) == 1
    assert output[0].final_confidence == 0.88

