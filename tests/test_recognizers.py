from pii_redactor.models import PIIType, TextBlock
from pii_redactor.recognizers import StructuredRecognizerSet, luhn_valid, verhoeff_valid


def block(text: str) -> TextBlock:
    return TextBlock("word/document.xml#p0", "word/document.xml", text, 0)


def test_structured_email_pan_and_dob():
    records = StructuredRecognizerSet("IN").detect([
        block("Contact email: alpha@example.com PAN: ABCDE1234F DOB: 12/04/1998")
    ])
    types = {item.pii_type for item in records}
    assert PIIType.EMAIL in types
    assert PIIType.PAN in types
    assert PIIType.DOB in types


def test_ordinary_date_is_not_dob():
    records = StructuredRecognizerSet("IN").detect([
        block("Board meeting held on 12/04/2024")
    ])
    assert PIIType.DOB not in {item.pii_type for item in records}


def test_luhn_and_verhoeff_validators():
    assert luhn_valid("4111 1111 1111 1111")
    assert not luhn_valid("4111 1111 1111 1112")
    assert verhoeff_valid("2943 6593 3461")

