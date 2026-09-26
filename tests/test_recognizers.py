from pii_redactor.models import PIIType, TextBlock
from pii_redactor.recognizers import (
    SpacyEntityRecognizer,
    StructuredRecognizerSet,
    luhn_valid,
    verhoeff_valid,
)


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


def test_all_required_structured_types_and_invalid_lookalikes():
    records = StructuredRecognizerSet("IN").detect([
        block(
            "Email: alpha@example.test Telephone: +91 98765 43210 Address: 42 Example Road, "
            "Sample Nagar, Delhi 110001 SSN: 123-45-6789 Payment card: 4111 1111 1111 1111 "
            "Date of birth: 14/03/1987 Client IP: 192.168.1.10"
        )
    ])
    types = {item.pii_type for item in records}
    assert {
        PIIType.EMAIL, PIIType.PHONE, PIIType.ADDRESS, PIIType.SSN,
        PIIType.CREDIT_CARD, PIIType.DOB, PIIType.IPV4,
    } <= types

    negatives = StructuredRecognizerSet("IN").detect([
        block(
            "Order 123456; Version 999.12.4.1000; Card-like 4111 1111 1111 1112; "
            "Board meeting held on 12/04/2024; Reference 123456789012345"
        )
    ])
    assert not ({PIIType.PHONE, PIIType.CREDIT_CARD, PIIType.DOB, PIIType.IPV4} & {
        item.pii_type for item in negatives
    })


def test_slash_separated_people_are_independent_spans():
    recognizer = SpacyEntityRecognizer("en_core_web_md")
    records = recognizer.detect([
        block("Lokesh Shah / Soumavo Sarkar"),
        TextBlock("word/document.xml#p1", "word/document.xml", "Kishan Rastogi / Abhijit Diwan", 1),
    ])
    values = {item.original_text for item in records if item.pii_type == PIIType.PERSON}
    assert values == {"Lokesh Shah", "Soumavo Sarkar", "Kishan Rastogi", "Abhijit Diwan"}
