from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document

from .models import PIIRecord


def file_sha256(path: str | Path) -> str:
    digest = sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_docx(path: str | Path) -> list[str]:
    errors: list[str] = []
    try:
        with ZipFile(path) as archive:
            bad = archive.testzip()
            if bad:
                errors.append(f"Corrupt ZIP member: {bad}")
            required = {"[Content_Types].xml", "word/document.xml"}
            missing = required - set(archive.namelist())
            if missing:
                errors.append(f"Missing DOCX parts: {sorted(missing)}")
    except BadZipFile as exc:
        errors.append(f"Invalid DOCX ZIP: {exc}")
    try:
        Document(path)
    except Exception as exc:
        errors.append(f"python-docx could not reopen output: {type(exc).__name__}: {exc}")
    return errors


def scan_original_values(path: str | Path, records: list[PIIRecord]) -> list[str]:
    originals = {
        item.original_text.casefold()
        for item in records
        if item.original_text and len(item.original_text.strip()) >= 4
    }
    with ZipFile(path) as archive:
        corpus_parts: list[str] = []
        for name in archive.namelist():
            if name.endswith((".xml", ".rels")):
                corpus_parts.append(archive.read(name).decode("utf-8", "ignore"))
        corpus = "\n".join(corpus_parts).casefold()
    return sorted(value for value in originals if value in corpus)


def replacement_application_failures(path: str | Path, records: list[PIIRecord]) -> list[str]:
    """Return approved native-text records whose safe replacement is absent from its output block."""
    from .docx_io import DocxPackage

    output_blocks = {block.block_id: block.text for block in DocxPackage(path).extract_blocks()}
    failures: list[str] = []
    for record in records:
        if record.source_kind != "native_text" or not record.replacement_value:
            continue
        if record.replacement_value not in output_blocks.get(record.block_id, ""):
            failures.append(record.record_id)
    return sorted(failures)


def media_hashes(path: str | Path) -> dict[str, str]:
    with ZipFile(path) as archive:
        return {
            name: sha256(archive.read(name)).hexdigest()
            for name in archive.namelist() if name.startswith("word/media/")
        }
