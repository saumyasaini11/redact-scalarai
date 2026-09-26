from io import BytesIO

from PIL import Image

from pii_redactor import media
from pii_redactor.ensemble import merge_and_score
from pii_redactor.models import PIIType, PolicyAction, ReviewStatus
from pii_redactor.policy import apply_entity_policy
from pii_redactor.policy import selected_media_replacements


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 40), "white").save(output, "PNG")
    return output.getvalue()


def _square_png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (100, 100), "white").save(output, "PNG")
    return output.getvalue()


def test_harmless_media_is_preserved_by_default(monkeypatch):
    monkeypatch.setattr(media.pytesseract, "image_to_string", lambda *args, **kwargs: "Company logo")
    monkeypatch.setattr(media, "_decode_qr", lambda image: "")
    records, replacements, inventory = media.analyze_media(
        {"word/media/logo.png": _png()}, "IN", "", replace_all=False
    )
    assert replacements == {}
    assert inventory[0]["sensitive_evidence"] is False
    assert inventory[0]["replaced"] is False
    assert records  # organization text remains detected for policy/reporting


def test_high_security_mode_replaces_all_media(monkeypatch):
    monkeypatch.setattr(media.pytesseract, "image_to_string", lambda *args, **kwargs: "")
    monkeypatch.setattr(media, "_decode_qr", lambda image: "")
    records, replacements, _ = media.analyze_media(
        {"word/media/logo.png": _png()}, "IN", "", replace_all=True
    )
    selected = selected_media_replacements(records, replacements, replace_all=True)
    assert set(selected) == {"word/media/logo.png"}


def test_ocr_pii_marks_media_sensitive(monkeypatch):
    monkeypatch.setattr(media.pytesseract, "image_to_string", lambda *args, **kwargs: "Email: alpha@example.test")
    monkeypatch.setattr(media, "_decode_qr", lambda image: "")
    records, replacements, inventory = media.analyze_media(
        {"word/media/contact.png": _png()}, "IN", "", replace_all=False
    )
    assert "word/media/contact.png" in replacements
    assert inventory[0]["sensitive_evidence"] is True
    assert any(record.original_text == "alpha@example.test" for record in records)


def test_undecoded_square_logo_is_audited_as_ignored_not_redacted(monkeypatch):
    monkeypatch.setattr(media.pytesseract, "image_to_string", lambda *args, **kwargs: "")
    monkeypatch.setattr(media, "_decode_qr", lambda image: "")
    records, replacements, inventory = media.analyze_media(
        {"word/media/logo.png": _square_png()}, "IN", "", replace_all=False
    )
    records = merge_and_score(records, 0.85, 0.60)
    apply_entity_policy(records)
    assert len(records) == 1
    assert records[0].pii_type == PIIType.QR_CODE
    assert records[0].review_status == ReviewStatus.REJECTED_AS_NON_PII
    assert records[0].policy_action == PolicyAction.IGNORE
    assert replacements == {}
    assert inventory[0]["sensitive_evidence"] is False


def test_decoded_qr_is_redacted_and_square_logo_can_be_replaced_in_high_security_mode(monkeypatch):
    monkeypatch.setattr(media.pytesseract, "image_to_string", lambda *args, **kwargs: "")
    monkeypatch.setattr(media, "_decode_qr", lambda image: "https://example.test/identity")
    records, replacements, _ = media.analyze_media(
        {"word/media/qr.png": _square_png()}, "IN", "", replace_all=False
    )
    records = merge_and_score(records, 0.85, 0.60)
    apply_entity_policy(records)
    assert records[0].policy_action == PolicyAction.REDACT
    assert set(selected_media_replacements(records, replacements)) == {"word/media/qr.png"}

    monkeypatch.setattr(media, "_decode_qr", lambda image: "")
    records, replacements, _ = media.analyze_media(
        {"word/media/logo.png": _square_png()}, "IN", "", replace_all=True
    )
    records = merge_and_score(records, 0.85, 0.60)
    apply_entity_policy(records)
    assert set(selected_media_replacements(records, replacements, replace_all=True)) == {
        "word/media/logo.png"
    }
