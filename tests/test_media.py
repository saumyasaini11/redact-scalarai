from io import BytesIO

from PIL import Image

from pii_redactor import media
from pii_redactor.policy import selected_media_replacements


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (80, 40), "white").save(output, "PNG")
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
