from pii_redactor.models import PIIRecord, PIIType
from pii_redactor.pseudonyms import Pseudonymizer
from pii_redactor.recognizers import luhn_valid


def record(pii_type: PIIType, value: str, identity: str = "person-1") -> PIIRecord:
    return PIIRecord(
        record_id=value, pii_type=pii_type, original_text=value,
        normalized_text=value.casefold(), source_kind="native_text",
        document_part="word/document.xml", block_id="b", start_offset=0,
        end_offset=len(value), identity_id=identity,
    )


def test_deterministic_and_linked_profile():
    first = Pseudonymizer("test-secret")
    second = Pseudonymizer("test-secret")
    name = record(PIIType.PERSON, "Original Person")
    email = record(PIIType.EMAIL, "original@example.com")
    assert first.replacement_for(name) == second.replacement_for(name)
    replacement_name = first.replacement_for(name)
    replacement_email = first.replacement_for(email)
    assert replacement_email.endswith("@example.test")
    assert replacement_name.casefold() != name.original_text.casefold()


def test_mask_mode():
    value = Pseudonymizer("test-secret", mode="mask").replacement_for(record(PIIType.PAN, "ABCDE1234F"))
    assert value.startswith("[PAN_")


def test_synthetic_required_values_are_deterministic_and_safe():
    generator = Pseudonymizer("test-secret")
    card = generator.replacement_for(record(PIIType.CREDIT_CARD, "4111 1111 1111 1111"))
    ip = generator.replacement_for(record(PIIType.IPV4, "192.168.1.10"))
    ssn = generator.replacement_for(record(PIIType.SSN, "123-45-6789"))
    assert luhn_valid(card)
    assert ip.startswith("198.51.100.")
    assert ssn.startswith("000-00-")
    assert card == Pseudonymizer("test-secret").replacement_for(
        record(PIIType.CREDIT_CARD, "4111 1111 1111 1111")
    )
