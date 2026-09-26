"""Build a shareable submission ZIP without source documents or private PII."""

from __future__ import annotations

from pathlib import Path
import subprocess
from zipfile import ZIP_DEFLATED, ZipFile

from build_evaluation_report import build_report


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DOCX = ROOT / "data" / "output" / "Red Herring Prospectus - Pseudonymized.docx"
ARCHIVE = ROOT / "dist" / "scalarai-pii-redaction-submission.zip"


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    paths = [ROOT / line for line in result.stdout.splitlines() if line.strip()]
    return [
        path for path in paths
        if path.is_file()
        and ".venv" not in path.parts
        and "data/private" not in path.as_posix()
        and "data/input" not in path.as_posix()
    ]


def main() -> int:
    if not OUTPUT_DOCX.exists():
        raise FileNotFoundError("Run the final redaction pipeline before building the submission")
    build_report()
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(ARCHIVE, "w", ZIP_DEFLATED) as archive:
        for path in repository_files():
            archive.write(path, path.relative_to(ROOT).as_posix())
        archive.write(OUTPUT_DOCX, f"deliverables/{OUTPUT_DOCX.name}")
    print(f"Created {ARCHIVE} ({ARCHIVE.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
