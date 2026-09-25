from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .config import load_settings
from .benchmark import run_required_type_benchmark
from .docx_io import DocxPackage
from .pipeline import run_pipeline
from .qa import file_sha256, validate_docx


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Offline confidence-aware DOCX PII pseudonymizer")
    parser.add_argument("--config", default="config.toml", help="Path to config.toml")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("inspect", help="Inventory the configured dataset")
    subparsers.add_parser("detect", help="Detect, report, and create a review draft")
    subparsers.add_parser("redact", help="Apply detections and review decisions")
    subparsers.add_parser("run-all", help="Run detection, review gating, output, evaluation, and QA")
    subparsers.add_parser("benchmark", help="Measure the frozen nine-type benchmark")
    verify = subparsers.add_parser("verify", help="Validate an existing DOCX")
    verify.add_argument("path", nargs="?", help="DOCX to verify; defaults to final then draft output")
    review = subparsers.add_parser("review", help="Show review queue information")
    review.add_argument("action", choices=["export", "apply"])
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    settings = load_settings(args.config)
    if args.command == "benchmark":
        report = run_required_type_benchmark(
            settings.reports_dir / "benchmark",
            default_region=settings.default_region,
            spacy_model=settings.spacy_model,
        )
        print(json.dumps({
            "all_required_types_detected": report["all_required_types_detected"],
            "micro": report["micro"],
            "report": str(settings.reports_dir / "benchmark" / "required_types_evaluation.md"),
        }, indent=2))
        return 0 if report["all_required_types_detected"] else 4
    if args.command == "inspect":
        package = DocxPackage(settings.input_path)
        package.extract_blocks()
        inventory = package.inventory()
        inventory["text_blocks"] = len(package.bindings)
        print(json.dumps(inventory, indent=2))
        return 0
    if args.command == "verify":
        if args.path:
            path = Path(args.path)
        elif settings.final_output_path.exists():
            path = settings.final_output_path
        else:
            path = settings.draft_output_path
        errors = validate_docx(path)
        print(json.dumps({
            "path": str(path.resolve()),
            "sha256": file_sha256(path) if path.exists() else None,
            "errors": errors,
        }, indent=2))
        return 1 if errors else 0
    if args.command == "review" and args.action == "export":
        queue = settings.private_dir / "review_queue.jsonl"
        count = len(queue.read_text(encoding="utf-8").splitlines()) if queue.exists() else 0
        print(json.dumps({"review_queue": str(queue), "items": count}, indent=2))
        return 0
    result = run_pipeline(settings)
    print(json.dumps({
        "output_path": str(result.output_path),
        "release_ready": result.release_ready,
        "record_count": result.record_count,
        "unresolved_count": result.unresolved_count,
        "qa_errors": result.qa_errors,
    }, indent=2))
    if result.qa_errors:
        return 3
    if not result.release_ready:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
