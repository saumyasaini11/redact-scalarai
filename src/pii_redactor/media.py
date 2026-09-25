from __future__ import annotations

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import textwrap

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import pytesseract

from .models import DetectionSource, Evidence, PIIRecord, PIIType, ReviewStatus, TextBlock
from .recognizers import StructuredRecognizerSet, normalize_value


IDENTITY_TERMS = (
    "date of birth", "dob", "permanent account number", "aadhaar", "unique identification",
    "father", "signature", "income tax", "government of india", "address",
)


def _media_record(name: str, pii_type: PIIType, original_text: str, score: float,
                  reason: str, source: DetectionSource, width: int, height: int) -> PIIRecord:
    digest = sha256(f"{name}|{pii_type.value}|{normalize_value(original_text)}".encode()).hexdigest()[:20]
    return PIIRecord(
        record_id=digest,
        pii_type=pii_type,
        original_text=original_text,
        normalized_text=normalize_value(original_text),
        source_kind="image",
        document_part=name,
        block_id=f"media:{name}",
        start_offset=0,
        end_offset=len(original_text),
        evidence=[Evidence(source, reason.replace(" ", "_").lower(), score, reason)],
        final_confidence=score,
        review_status=ReviewStatus.AUTO_APPROVED if score >= 0.85 else ReviewStatus.NEEDS_REVIEW,
        media_name=name,
        bounding_box=(0, 0, width, height),
    )


def _decode_qr(image: Image.Image) -> str:
    array = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2BGR)
    value, points, _ = cv2.QRCodeDetector().detectAndDecode(array)
    return value or ""


def _placeholder(image: Image.Image, name: str, output_format: str) -> bytes:
    width, height = image.size
    background = Image.new("RGB", (max(width, 64), max(height, 40)), "#E6E8EB")
    draw = ImageDraw.Draw(background)
    font = ImageFont.load_default()
    label = f"SYNTHETIC REDACTED IMAGE\n{sha256(name.encode()).hexdigest()[:10].upper()}"
    lines = textwrap.wrap(label.replace("\n", " "), width=max(12, min(40, width // 8)))
    text = "\n".join(lines)
    box = draw.multiline_textbbox((0, 0), text, font=font, align="center", spacing=4)
    text_width = box[2] - box[0]
    text_height = box[3] - box[1]
    draw.multiline_text(
        ((background.width - text_width) / 2, (background.height - text_height) / 2),
        text,
        fill="#333333",
        font=font,
        align="center",
        spacing=4,
    )
    output = BytesIO()
    fmt = "JPEG" if output_format.upper() in {"JPG", "JPEG"} else "PNG"
    background.save(output, format=fmt, quality=90)
    return output.getvalue()


def analyze_media(media: dict[str, bytes], default_region: str, tesseract_cmd: str,
                  replace_all: bool = True) -> tuple[list[PIIRecord], dict[str, bytes], list[dict]]:
    if tesseract_cmd:
        candidate = Path(tesseract_cmd)
        if candidate.exists():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
    records: list[PIIRecord] = []
    replacements: dict[str, bytes] = {}
    inventory: list[dict] = []
    structured = StructuredRecognizerSet(default_region)

    for name, data in media.items():
        try:
            image = Image.open(BytesIO(data))
            image.load()
        except Exception:
            inventory.append({"media_name": name, "readable": False, "replaced": False})
            continue
        width, height = image.size
        try:
            ocr_text = pytesseract.image_to_string(image, lang="eng", config="--psm 6").strip()
        except Exception:
            ocr_text = ""
        try:
            qr_value = _decode_qr(image)
        except Exception:
            qr_value = ""

        if ocr_text:
            block = TextBlock(
                block_id=f"media:{name}",
                part_name=name,
                text=ocr_text,
                paragraph_index=0,
            )
            for record in structured.detect([block]):
                record.source_kind = "ocr_text"
                record.media_name = name
                record.bounding_box = (0, 0, width, height)
                record.document_part = name
                record.evidence.append(Evidence(
                    DetectionSource.OCR, "tesseract_ocr", 0.55,
                    "Value detected in locally extracted OCR text",
                ))
                records.append(record)

        lower = ocr_text.casefold()
        identity_hits = [term for term in IDENTITY_TERMS if term in lower]
        if identity_hits or (width >= 500 and height >= 500):
            records.append(_media_record(
                name, PIIType.BIOMETRIC, "identity-document-media", 0.98,
                "Identity document, face, or signature media", DetectionSource.OCR, width, height,
            ))
        elif ocr_text:
            records.append(_media_record(
                name, PIIType.COMPANY, ocr_text[:160], 0.85,
                "Commercial logo or organization text in media", DetectionSource.OCR, width, height,
            ))
        if qr_value or (width <= 400 and height <= 400 and abs(width - height) <= max(width, height) * 0.35):
            records.append(_media_record(
                name, PIIType.QR_CODE, qr_value or "undecoded-qr-like-media", 0.98,
                "QR code or machine-readable square media", DetectionSource.QR_DETECTOR, width, height,
            ))

        sensitive = replace_all or bool(identity_hits or qr_value or ocr_text)
        if sensitive:
            extension = Path(name).suffix.lstrip(".") or image.format or "PNG"
            replacements[name] = _placeholder(image, name, extension)
        inventory.append({
            "media_name": name,
            "width": width,
            "height": height,
            "source_sha256": sha256(data).hexdigest(),
            "ocr_characters": len(ocr_text),
            "qr_decoded": bool(qr_value),
            "identity_terms": identity_hits,
            "replaced": sensitive,
        })
    return records, replacements, inventory

