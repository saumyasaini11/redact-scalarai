from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Iterable
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from .models import PIIRecord, TextBlock


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CP_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
DC_NS = "http://purl.org/dc/elements/1.1/"
EP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"
R_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
NS = {"w": W_NS}


@dataclass
class NodeSlice:
    node: etree._Element
    start: int
    end: int


@dataclass
class BlockBinding:
    block: TextBlock
    slices: list[NodeSlice]


class DocxPackage:
    TEXT_PART_PREFIXES = (
        "word/document.xml",
        "word/header",
        "word/footer",
        "word/footnotes.xml",
        "word/endnotes.xml",
        "word/comments.xml",
    )

    def __init__(self, path: str | Path):
        self.path = Path(path).resolve()
        self.entries: dict[str, bytes] = {}
        self.roots: dict[str, etree._Element] = {}
        self.bindings: dict[str, BlockBinding] = {}
        with ZipFile(self.path) as archive:
            for name in archive.namelist():
                self.entries[name] = archive.read(name)
        for name, data in self.entries.items():
            if (
                name.endswith(".rels")
                or name.endswith(".xml")
                and (
                    name.startswith("word/")
                    or name.startswith("docProps/")
                    or name == "[Content_Types].xml"
                )
            ):
                try:
                    self.roots[name] = etree.fromstring(data)
                except etree.XMLSyntaxError:
                    continue

    @property
    def source_hash(self) -> str:
        digest = sha256()
        with self.path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def inventory(self) -> dict[str, object]:
        media = [name for name in self.entries if name.startswith("word/media/")]
        text_parts = [name for name in self.roots if self._is_text_part(name)]
        return {
            "input_path": str(self.path),
            "sha256": self.source_hash,
            "package_parts": len(self.entries),
            "text_parts": len(text_parts),
            "media_parts": len(media),
            "media_names": media,
        }

    def _is_text_part(self, name: str) -> bool:
        return name == "word/document.xml" or any(
            name.startswith(prefix) for prefix in self.TEXT_PART_PREFIXES[1:]
        )

    def extract_blocks(self) -> list[TextBlock]:
        blocks: list[TextBlock] = []
        self.bindings.clear()
        for part_name in sorted(self.roots):
            if not self._is_text_part(part_name):
                continue
            root = self.roots[part_name]
            paragraphs = root.xpath("//w:p", namespaces=NS)
            for paragraph_index, paragraph in enumerate(paragraphs):
                nodes = paragraph.xpath(".//w:t", namespaces=NS)
                cursor = 0
                slices: list[NodeSlice] = []
                pieces: list[str] = []
                for node in nodes:
                    value = node.text or ""
                    pieces.append(value)
                    slices.append(NodeSlice(node=node, start=cursor, end=cursor + len(value)))
                    cursor += len(value)
                text = "".join(pieces)
                if not text.strip():
                    continue
                block_id = f"{part_name}#p{paragraph_index}"
                block = TextBlock(
                    block_id=block_id,
                    part_name=part_name,
                    text=text,
                    paragraph_index=paragraph_index,
                    table_context=self._table_context(paragraph),
                )
                blocks.append(block)
                self.bindings[block_id] = BlockBinding(block=block, slices=slices)
        return blocks

    @staticmethod
    def _table_context(paragraph: etree._Element) -> str:
        cells = paragraph.xpath("ancestor::w:tc[1]", namespaces=NS)
        if not cells:
            return ""
        cell = cells[0]
        row = cell.xpath("ancestor::w:tr[1]", namespaces=NS)
        if not row:
            return "table-cell"
        values: list[str] = []
        for tc in row[0].xpath("./w:tc", namespaces=NS):
            value = "".join(tc.xpath(".//w:t/text()", namespaces=NS)).strip()
            if value:
                values.append(value[:120])
        return " | ".join(values[:8])

    def media(self) -> dict[str, bytes]:
        return {
            name: data
            for name, data in self.entries.items()
            if name.startswith("word/media/")
        }

    def replace_media(self, replacements: dict[str, bytes]) -> None:
        for name, data in replacements.items():
            if name not in self.entries:
                raise KeyError(f"Media part does not exist: {name}")
            self.entries[name] = data

    def apply_records(self, records: Iterable[PIIRecord]) -> None:
        records = list(records)
        grouped: dict[str, list[PIIRecord]] = defaultdict(list)
        for record in records:
            if record.source_kind == "native_text" and record.replacement_value is not None:
                grouped[record.block_id].append(record)
        for block_id, items in grouped.items():
            binding = self.bindings.get(block_id)
            if not binding:
                continue
            for record in sorted(items, key=lambda item: item.start_offset, reverse=True):
                self._replace_span(binding.slices, record.start_offset, record.end_offset, record.replacement_value or "")
        self._replace_remaining_text(records)
        self._replace_relationship_targets(records)

    def _replace_remaining_text(self, records: list[PIIRecord]) -> None:
        """Replace approved repeats that were not emitted as separate detector spans."""
        replacements: dict[str, str] = {}
        for record in records:
            if record.source_kind == "native_text" and record.original_text and record.replacement_value:
                replacements.setdefault(record.original_text.casefold(), record.replacement_value)
        if not replacements:
            return

        def bounded(value: str) -> str:
            prefix = r"(?<!\w)" if value[0].isalnum() else ""
            suffix = r"(?!\w)" if value[-1].isalnum() else ""
            return prefix + re.escape(value) + suffix

        ordered = sorted(replacements, key=len, reverse=True)
        pattern = re.compile("|".join(bounded(key) for key in ordered), re.IGNORECASE)
        safe_values = sorted(set(replacements.values()), key=len, reverse=True)
        safe_pattern = re.compile(
            "|".join(re.escape(value) for value in safe_values),
            re.IGNORECASE,
        )
        for binding in self.bindings.values():
            nodes = [item.node for item in binding.slices]
            text = "".join(node.text or "" for node in nodes)
            if not text:
                continue
            protected_ranges = [
                (match.start(), match.end())
                for match in safe_pattern.finditer(text)
            ]
            matches = [
                match for match in pattern.finditer(text)
                if not any(match.start() < end and match.end() > start for start, end in protected_ranges)
            ]
            cursor = 0
            slices: list[NodeSlice] = []
            for node in nodes:
                value = node.text or ""
                slices.append(NodeSlice(node=node, start=cursor, end=cursor + len(value)))
                cursor += len(value)
            for match in reversed(matches):
                self._replace_span(
                    slices,
                    match.start(),
                    match.end(),
                    replacements[match.group(0).casefold()],
                )

    def _replace_relationship_targets(self, records: list[PIIRecord]) -> None:
        replacements = {
            record.original_text: record.replacement_value
            for record in records
            if record.original_text and record.replacement_value
        }
        if not replacements:
            return
        ordered = sorted(replacements, key=len, reverse=True)
        lookup = {key.casefold(): value for key, value in replacements.items()}
        pattern = re.compile("|".join(re.escape(key) for key in ordered), re.IGNORECASE)
        for name, root in self.roots.items():
            if not name.endswith(".rels"):
                continue
            for element in root.iter():
                if element.get("TargetMode") != "External":
                    continue
                target = element.get("Target")
                if not target:
                    continue
                element.set("Target", pattern.sub(lambda match: lookup[match.group(0).casefold()], target))

    @staticmethod
    def _replace_span(slices: list[NodeSlice], start: int, end: int, replacement: str) -> None:
        affected = [item for item in slices if item.end > start and item.start < end]
        if not affected:
            return
        first = affected[0]
        last = affected[-1]
        if first is last:
            value = first.node.text or ""
            local_start = max(0, start - first.start)
            local_end = min(len(value), end - first.start)
            first.node.text = value[:local_start] + replacement + value[local_end:]
            return

        first_value = first.node.text or ""
        first_cut = max(0, start - first.start)
        first.node.text = first_value[:first_cut] + replacement
        for middle in affected[1:-1]:
            middle.node.text = ""
        last_value = last.node.text or ""
        last_cut = min(len(last_value), end - last.start)
        last.node.text = last_value[last_cut:]

    def scrub_metadata(self) -> None:
        core = self.roots.get("docProps/core.xml")
        if core is not None:
            for xpath in ("//dc:creator", "//cp:lastModifiedBy"):
                for node in core.xpath(xpath, namespaces={"dc": DC_NS, "cp": CP_NS}):
                    node.text = ""
        app = self.roots.get("docProps/app.xml")
        if app is not None:
            for local_name in ("Company", "Manager"):
                for node in app.xpath(f"//*[local-name()='{local_name}']"):
                    node.text = ""
        for name, root in self.roots.items():
            if not name.startswith("word/"):
                continue
            for element in root.iter():
                for attr_name in list(element.attrib):
                    if etree.QName(attr_name).localname.startswith("rsid"):
                        del element.attrib[attr_name]

        if "docProps/custom.xml" in self.entries:
            self.entries.pop("docProps/custom.xml", None)
            self.roots.pop("docProps/custom.xml", None)
            rels = self.roots.get("_rels/.rels")
            if rels is not None:
                for rel in list(rels):
                    if (rel.get("Target") or "").endswith("docProps/custom.xml"):
                        rels.remove(rel)
            content_types = self.roots.get("[Content_Types].xml")
            if content_types is not None:
                for child in list(content_types):
                    if child.get("PartName") == "/docProps/custom.xml":
                        content_types.remove(child)

    def save(self, output_path: str | Path) -> Path:
        output = Path(output_path).resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        xml_bytes: dict[str, bytes] = {}
        for name, root in self.roots.items():
            xml_bytes[name] = etree.tostring(
                root,
                encoding="UTF-8",
                xml_declaration=True,
                standalone=True,
            )
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for name, data in self.entries.items():
                archive.writestr(name, xml_bytes.get(name, data))
        return output


def extracted_text(path: str | Path) -> str:
    package = DocxPackage(path)
    return "\n".join(block.text for block in package.extract_blocks())
