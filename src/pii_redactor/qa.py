from __future__ import annotations

from hashlib import sha256
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from docx import Document
from lxml import etree

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


def _structure_signature(path: str | Path) -> dict[str, int]:
    names = {
        "paragraphs": "p", "tables": "tbl", "rows": "tr", "cells": "tc",
        "sections": "sectPr", "drawings": "drawing", "headers": "headerReference",
        "footers": "footerReference",
    }
    counts = {key: 0 for key in names}
    with ZipFile(path) as archive:
        for part_name in archive.namelist():
            if not part_name.startswith("word/") or not part_name.endswith(".xml"):
                continue
            try:
                root = etree.fromstring(archive.read(part_name))
            except etree.XMLSyntaxError:
                continue
            for key, local_name in names.items():
                counts[key] += len(root.xpath(f"//*[local-name()='{local_name}']"))
    return counts


def validate_structure_preservation(source_path: str | Path, output_path: str | Path) -> list[str]:
    source = _structure_signature(source_path)
    output = _structure_signature(output_path)
    errors: list[str] = []
    for key in source:
        if source[key] != output[key]:
            errors.append(f"DOCX structure changed for {key}: source={source[key]}, output={output[key]}")
    return errors
