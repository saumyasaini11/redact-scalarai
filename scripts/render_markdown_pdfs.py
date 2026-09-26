"""Create readable PDF copies of the project's Markdown deliverables."""

from __future__ import annotations

from hashlib import sha256
from html import escape
import json
from pathlib import Path
import textwrap


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output" / "pdf"
SOURCES = (
    ROOT / "README.md",
    ROOT / "docs" / "RHP_QA_REPORT.md",
    ROOT / "docs" / "REDACTION_TRACKER.md",
    ROOT / "reports" / "benchmark" / "required_types_evaluation.md",
    ROOT / "docs" / "EVALUATION_REPORT.md",
)
MANIFEST = OUTPUT_DIR / "source_hashes.json"


def _pdf_path(source: Path) -> Path:
    return OUTPUT_DIR / f"{source.stem}.pdf"


def pdfs_current() -> bool:
    if not MANIFEST.exists():
        return False
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return manifest.get("_renderer_sha256") == sha256(Path(__file__).read_bytes()).hexdigest() and all(
        source.exists()
        and _pdf_path(source).exists()
        and manifest.get(source.relative_to(ROOT).as_posix()) == sha256(source.read_bytes()).hexdigest()
        for source in SOURCES
    )


def _font_names() -> tuple[str, str, str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidates = (
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
            Path("C:/Windows/Fonts/ariali.ttf"),
            Path("C:/Windows/Fonts/consola.ttf"),
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"),
        ),
    )
    for regular, bold, italic, mono in candidates:
        if all(path.exists() for path in (regular, bold, italic, mono)):
            for name, path in zip(("DocSans", "DocSans-Bold", "DocSans-Italic", "DocMono"),
                                  (regular, bold, italic, mono)):
                if name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(name, str(path)))
            pdfmetrics.registerFontFamily("DocSans", normal="DocSans", bold="DocSans-Bold",
                                          italic="DocSans-Italic", boldItalic="DocSans-Bold")
            return "DocSans", "DocSans-Bold", "DocSans-Italic", "DocMono"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


def _inline(token) -> str:
    if not token.children:
        return escape(token.content)
    result: list[str] = []
    link_tags: list[str] = []
    for child in token.children:
        kind = child.type
        if kind == "text":
            result.append(escape(child.content))
        elif kind == "code_inline":
            result.append(f'<font face="DocMono">{escape(child.content)}</font>')
        elif kind == "strong_open":
            result.append("<b>")
        elif kind == "strong_close":
            result.append("</b>")
        elif kind == "em_open":
            result.append("<i>")
        elif kind == "em_close":
            result.append("</i>")
        elif kind == "link_open":
            href = child.attrGet("href") or ""
            if href.startswith(("https://", "http://", "mailto:")):
                result.append(f'<link href="{escape(href, quote=True)}" color="#1E5AA6">')
                link_tags.append("link")
            else:
                # Markdown section/file links are for the repository; they do not
                # define PDF destinations in this standalone readable copy.
                result.append('<font color="#1E5AA6">')
                link_tags.append("font")
        elif kind == "link_close":
            result.append(f"</{link_tags.pop()}>")
        elif kind == "image":
            result.append(escape(child.content or "image"))
        elif kind == "hardbreak":
            result.append("<br/>")
        elif kind == "softbreak":
            result.append(" ")
        elif kind == "html_inline":
            result.append(escape(child.content))
    return "".join(result)


def _table(tokens, start: int, styles, width: float):
    from reportlab.lib import colors
    from reportlab.platypus import LongTable, Paragraph, TableStyle

    rows: list[list] = []
    row: list = []
    header = False
    index = start + 1
    while index < len(tokens) and tokens[index].type != "table_close":
        token = tokens[index]
        if token.type == "thead_open":
            header = True
        elif token.type == "thead_close":
            header = False
        elif token.type == "tr_open":
            row = []
        elif token.type == "inline":
            row.append(Paragraph(_inline(token), styles["TableHeader" if header else "TableCell"]))
        elif token.type == "tr_close":
            rows.append(row)
        index += 1
    columns = max((len(row) for row in rows), default=1)
    column_widths = (
        [82] + [(width - 82) / (columns - 1)] * (columns - 1)
        if columns >= 5 else [width / columns] * columns
    )
    table = LongTable(rows, colWidths=column_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF0F7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#CBD5E1")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table, index, len(rows)


def _render(source: Path, target: Path) -> None:
    from markdown_it import MarkdownIt
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import HRFlowable, KeepTogether, Paragraph, Preformatted, SimpleDocTemplate, Spacer

    regular, bold, italic, mono = _font_names()
    styles = {
        "Body": ParagraphStyle("Body", fontName=regular, fontSize=9.5, leading=14,
                               textColor=colors.HexColor("#243247"), spaceAfter=6,
                               allowOrphans=False, allowWidows=False),
        "H1": ParagraphStyle("H1", fontName=bold, fontSize=20, leading=25,
                             textColor=colors.HexColor("#17365D"), spaceAfter=14, keepWithNext=True),
        "H2": ParagraphStyle("H2", fontName=bold, fontSize=14, leading=19,
                             textColor=colors.HexColor("#17365D"), spaceBefore=16, spaceAfter=9,
                             keepWithNext=True),
        "H3": ParagraphStyle("H3", fontName=bold, fontSize=11, leading=15,
                             textColor=colors.HexColor("#17365D"), spaceBefore=12, spaceAfter=7,
                             keepWithNext=True),
        "Lead": ParagraphStyle("Lead", fontName=regular, fontSize=9.5, leading=14,
                               textColor=colors.HexColor("#243247"), spaceAfter=6,
                               keepWithNext=True),
        "List": ParagraphStyle("List", fontName=regular, fontSize=9.5, leading=14,
                               leftIndent=18, firstLineIndent=-12, spaceAfter=4),
        "Code": ParagraphStyle("Code", fontName=mono, fontSize=7.5, leading=10.2,
                               leftIndent=10, spaceBefore=5, spaceAfter=10,
                               backColor=colors.HexColor("#F2F5F9")),
        "TableHeader": ParagraphStyle("TableHeader", fontName=bold, fontSize=7.5,
                                      leading=10, alignment=TA_LEFT),
        "TableCell": ParagraphStyle("TableCell", fontName=regular, fontSize=7.5,
                                    leading=10, alignment=TA_LEFT),
    }
    if source.name == "EVALUATION_REPORT.md":
        styles["Body"].leading = 13
        styles["Body"].spaceAfter = 4
        styles["H2"].spaceBefore = 12
        styles["H2"].spaceAfter = 7
        styles["H3"].spaceBefore = 9
        styles["H3"].spaceAfter = 6
        styles["List"].leading = 13
        styles["List"].spaceAfter = 2
    if regular != "DocSans":
        # The PDF build is meant for bundled/desktop use with a Unicode TTF font.
        raise RuntimeError("Arial or DejaVu fonts are required for readable Markdown PDFs")

    page_width, _ = A4
    usable_width = page_width - 94
    tokens = MarkdownIt("commonmark").enable("table").parse(source.read_text(encoding="utf-8"))
    story: list = []
    list_stack: list[dict] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        kind = token.type
        if kind == "table_open":
            table, index, row_count = _table(tokens, index, styles, usable_width)
            if row_count <= 10:
                members = [table]
                if story and isinstance(story[-1], Paragraph) and story[-1].style.name.startswith("H"):
                    members.insert(0, story.pop())
                story.append(KeepTogether(members))
            else:
                story.append(table)
            story.append(Spacer(1, 11))
        elif kind == "heading_open":
            level = min(int(token.tag[1:]), 3)
            story.append(Paragraph(_inline(tokens[index + 1]), styles[f"H{level}"]))
            index += 2
        elif kind == "paragraph_open":
            content = _inline(tokens[index + 1])
            if list_stack:
                current = list_stack[-1]
                current["count"] += 1
                marker = f"{current['count']}." if current["ordered"] else "&#8226;"
                story.append(Paragraph(f"{marker}  {content}", styles["List"]))
            else:
                story.append(Paragraph(content, styles["Lead" if content.rstrip().endswith(":") else "Body"]))
            index += 2
        elif kind in {"bullet_list_open", "ordered_list_open"}:
            list_stack.append({"ordered": kind == "ordered_list_open", "count": 0})
        elif kind in {"bullet_list_close", "ordered_list_close"}:
            list_stack.pop()
        elif kind in {"fence", "code_block"}:
            wrapped = "\n".join(
                "\n".join(textwrap.wrap(line, width=95, replace_whitespace=False, drop_whitespace=False))
                if len(line) > 95 else line
                for line in token.content.rstrip("\n").splitlines()
            )
            story.append(Preformatted(wrapped, styles["Code"]))
        elif kind == "hr":
            story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#CBD5E1")))
        index += 1

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setStrokeColor(colors.HexColor("#CBD5E1"))
        canvas.line(47, 42, page_width - 47, 42)
        canvas.setFont(regular, 8)
        canvas.setFillColor(colors.HexColor("#64748B"))
        canvas.drawString(47, 29, source.name)
        canvas.drawRightString(page_width - 47, 29, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(target), pagesize=A4, leftMargin=47, rightMargin=47,
                            topMargin=48, bottomMargin=55, title=source.stem.replace("_", " "),
                            author="DOCX PII Redactor")
    doc.build(story, onFirstPage=footer, onLaterPages=footer)


def build_pdfs() -> list[Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, str] = {"_renderer_sha256": sha256(Path(__file__).read_bytes()).hexdigest()}
    paths: list[Path] = []
    for source in SOURCES:
        if not source.exists():
            raise FileNotFoundError(source)
        target = _pdf_path(source)
        _render(source, target)
        manifest[source.relative_to(ROOT).as_posix()] = sha256(source.read_bytes()).hexdigest()
        paths.append(target)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return paths


def main() -> int:
    for path in build_pdfs():
        print(f"Created {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
