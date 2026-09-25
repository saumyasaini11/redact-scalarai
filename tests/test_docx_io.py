from pathlib import Path

from docx import Document

from pii_redactor.docx_io import DocxPackage, extracted_text
from pii_redactor.models import PIIRecord, PIIType


def test_cross_run_replacement():
    work = Path(".tmp")
    work.mkdir(exist_ok=True)
    source = work / "test-cross-run-source.docx"
    output = work / "test-cross-run-output.docx"
    doc = Document()
    paragraph = doc.add_paragraph()
    paragraph.add_run("john.")
    paragraph.add_run("smith@example.com")
    doc.save(source)

    try:
        package = DocxPackage(source)
        blocks = package.extract_blocks()
        target = blocks[0]
        record = PIIRecord(
            record_id="email", pii_type=PIIType.EMAIL,
            original_text=target.text, normalized_text=target.text,
            source_kind="native_text", document_part=target.part_name,
            block_id=target.block_id, start_offset=0, end_offset=len(target.text),
            replacement_value="user@example.test",
        )
        package.apply_records([record])
        package.save(output)
        assert "user@example.test" in extracted_text(output)
        assert "john.smith@example.com" not in extracted_text(output)
    finally:
        source.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
