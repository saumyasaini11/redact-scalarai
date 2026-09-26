from __future__ import annotations

import json
from pathlib import Path
import secrets
import sys

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from pii_redactor.app_service import (
    AppRun,
    build_download_bundle,
    create_app_run,
    finalize_pending_privacy_first,
    read_jsonl,
    save_review_decisions,
)
from pii_redactor.benchmark import run_required_type_benchmark
from pii_redactor.pipeline import run_pipeline


DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _clear_active_result() -> None:
    st.session_state.pop("app_run", None)
    st.session_state.pop("pipeline_result", None)


def _download_file(path: Path, mime: str) -> None:
    if path.exists():
        st.download_button(path.name, path.read_bytes(), path.name, mime)


st.set_page_config(page_title="DOCX PII Redactor", layout="wide")
st.title("DOCX PII Redactor")
st.caption("Upload a Word document, review detected PII, and download a pseudonymized copy.")

st.subheader("1. Input")
uploaded = st.file_uploader(
    "Upload a .docx file",
    type=["docx"],
    key="source_docx",
    on_change=_clear_active_result,
)
if uploaded:
    st.caption(f"Selected: {uploaded.name}")

st.subheader("2. Configure")
mode_label = st.selectbox(
    "Replacement mode",
    ["Synthetic pseudonyms", "Mask (obvious redaction)", "Partial masking"],
    help="Synthetic mode substitutes deterministic fake alternatives.",
)
mode = {
    "Mask (obvious redaction)": "mask",
    "Synthetic pseudonyms": "synthetic",
    "Partial masking": "partial",
}[mode_label]
company_scope = st.selectbox(
    "Corporate entity policy",
    ["protect", "review", "redact"],
    help="Protect keeps legitimate company names and corporate identifiers unchanged while reporting detections.",
)
replace_all_media = st.checkbox(
    "High-security mode: replace all embedded media",
    value=False,
    help="Off replaces only media with PII, identity, or QR evidence. On also replaces harmless graphics.",
)
with st.expander("More processing options"):
    high_threshold = st.slider("Automatic approval threshold", 0.70, 0.99, 0.85, 0.01)
    medium_threshold = st.slider("Review threshold", 0.30, high_threshold, 0.60, 0.01)
    default_region = st.text_input("Phone region", "IN", max_chars=2).upper()
    seed = st.text_input(
        "Private deterministic seed",
        value=st.session_state.setdefault("seed", secrets.token_urlsafe(24)),
        type="password",
        help="The seed stays local and keeps replacements consistent for repeated identities.",
    )
    gold_upload = st.file_uploader(
        "Optional gold annotations",
        type=["jsonl"],
        help="Provide labeled spans for document-specific precision, recall, and F1.",
    )

st.subheader("3. Redact")
if st.button("Run Redaction", type="primary", disabled=uploaded is None):
    try:
        app_run = create_app_run(
            PROJECT_ROOT,
            uploaded.name,
            uploaded.getvalue(),
            seed=seed,
            mode=mode,
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
            default_region=default_region,
            replace_all_media=replace_all_media,
            company_scope=company_scope,
            auto_redact_pending=False,
            tesseract_cmd="",
        )
        if gold_upload:
            (app_run.settings.private_dir / "gold_annotations.jsonl").write_bytes(gold_upload.getvalue())
        with st.spinner("Analyzing and redacting the document…"):
            result = run_pipeline(app_run.settings)
        st.session_state["app_run"] = app_run
        st.session_state["pipeline_result"] = result
    except ValueError as exc:
        st.error(str(exc))
    except Exception as exc:
        st.exception(exc)

app_run: AppRun | None = st.session_state.get("app_run")
result = st.session_state.get("pipeline_result")

if app_run and result:
    summary_path = app_run.settings.reports_dir / "summary_report.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    st.subheader("4. Result")
    if result.release_ready:
        st.success("Redaction complete. The DOCX passed review gating and automated QA.")
    else:
        st.warning(
            f"Review draft ready. {result.unresolved_count} policy decisions and "
            f"{len(result.qa_errors)} QA findings remain."
        )
    metrics = st.columns(4)
    metrics[0].metric("PII detected", summary.get("total_candidates", result.record_count))
    metrics[1].metric("Redacted", summary.get("redacted_entities", 0))
    metrics[2].metric("Protected", summary.get("protected_entities", 0))
    metrics[3].metric("Needs review", result.unresolved_count)

    queue = read_jsonl(app_run.settings.private_dir / "review_queue.jsonl")
    if queue:
        with st.expander(f"Review {len(queue)} pending detections", expanded=True):
            source_hash = queue[0]["source_hash"]
            types = sorted({item["pii_type"] for item in queue})
            selected_types = st.multiselect("Filter by type", types, default=types)
            visible = [item for item in queue if item["pii_type"] in selected_types]
            rows = [{
                "record_id": item["record_id"],
                "type": item["pii_type"],
                "value": item["original_text"],
                "confidence": round(float(item["final_confidence"]), 3),
                "part": item["document_part"],
                "decision": "",
                "new_type": "",
                "identity_id": item.get("identity_id") or "",
                "note": "",
            } for item in visible]
            st.caption("Review values stay local and are excluded from the shareable bundle.")
            edited = st.data_editor(
                rows,
                width="stretch",
                hide_index=True,
                disabled=["record_id", "type", "value", "confidence", "part"],
                column_config={
                    "decision": st.column_config.SelectboxColumn(
                        "Decision",
                        options=["", "REDACT", "PROTECT", "IGNORE", "APPROVE", "RETYPE", "LINK_IDENTITY", "UNLINK_IDENTITY"],
                    ),
                    "confidence": st.column_config.NumberColumn(format="%.3f"),
                },
                key=f"review-{app_run.run_id}",
            )
            if st.button("Save review decisions"):
                saved = save_review_decisions(
                    app_run.settings.private_dir / "review_decisions.jsonl", edited, source_hash
                )
                st.success(f"Saved {saved} decisions.")
            if st.button("Apply decisions and regenerate"):
                try:
                    save_review_decisions(
                        app_run.settings.private_dir / "review_decisions.jsonl", edited, source_hash
                    )
                    with st.spinner("Regenerating the DOCX and checking the output…"):
                        st.session_state["pipeline_result"] = run_pipeline(app_run.settings)
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)
            if st.button(f"Privacy-first finalize all {len(queue)} pending items"):
                try:
                    finalize_pending_privacy_first(
                        app_run.settings.private_dir / "review_decisions.jsonl", queue
                    )
                    with st.spinner("Applying policy decisions and checking the output…"):
                        st.session_state["pipeline_result"] = run_pipeline(app_run.settings)
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)

    with st.expander("View detection and QA details"):
        details = st.columns(3)
        details[0].metric("Ignored", summary.get("ignored_entities", 0))
        details[1].metric("Media replaced", f"{summary.get('media_replaced', 0)}/{summary.get('media_total', 0)}")
        details[2].metric("QA findings", len(result.qa_errors))
        if summary.get("entities_by_type"):
            st.dataframe(
                [{"PII type": name, "Candidates": count} for name, count in summary["entities_by_type"].items()],
                width="stretch",
                hide_index=True,
            )
        if result.qa_errors:
            st.error("; ".join(result.qa_errors))
        qa_path = app_run.root / "docs" / "RHP_QA_REPORT.md"
        if qa_path.exists():
            st.markdown(qa_path.read_text(encoding="utf-8"))

st.subheader("5. Deliverables")
if app_run and result:
    output_path = result.output_path
    report_root = app_run.settings.reports_dir
    docs_root = app_run.root / "docs"
    st.caption("Current run · final DOCX" if result.release_ready else "Current run · review draft")
else:
    output_path = PROJECT_ROOT / "data" / "output" / "Red Herring Prospectus - Pseudonymized.docx"
    report_root = PROJECT_ROOT / "reports"
    docs_root = PROJECT_ROOT / "docs"
    st.caption("Supplied RHP · previously generated files")

deliverables = [
    (output_path, DOCX_MIME),
    (docs_root / "RHP_QA_REPORT.md", "text/markdown"),
    (report_root / "summary_report.json", "application/json"),
    (report_root / "rhp_release_validation.csv", "text/csv"),
    (docs_root / "REDACTION_TRACKER.md", "text/markdown"),
]
download_columns = st.columns(2)
for index, (path, mime) in enumerate(deliverables):
    with download_columns[index % 2]:
        _download_file(path, mime)
if app_run and result:
    st.download_button(
        f"pii-redaction-{app_run.run_id}.zip",
        build_download_bundle(app_run, result.output_path),
        f"pii-redaction-{app_run.run_id}.zip",
        "application/zip",
    )
else:
    _download_file(PROJECT_ROOT / "dist" / "scalarai-pii-redaction-submission.zip", "application/zip")

with st.expander("More reports and benchmark"):
    _download_file(report_root / "pii_detection_log.sanitized.jsonl", "application/json")
    _download_file(PROJECT_ROOT / "docs" / "EVALUATION_REPORT.md", "text/markdown")
    st.write(
        "The frozen benchmark measures all nine required PII types. Its results describe the "
        "controlled benchmark, not an uploaded document unless gold annotations are supplied."
    )
    if st.button("Run required-type benchmark"):
        try:
            with st.spinner("Evaluating the frozen benchmark…"):
                st.session_state["benchmark_report"] = run_required_type_benchmark(
                    PROJECT_ROOT / "reports" / "benchmark"
                )
        except Exception as exc:
            st.exception(exc)
    benchmark_report = st.session_state.get("benchmark_report")
    if benchmark_report:
        micro = benchmark_report["micro"]
        classification = benchmark_report["block_classification"]
        metrics = st.columns(5)
        metrics[0].metric("Block accuracy", f"{classification['accuracy']:.3f}")
        metrics[1].metric("Span precision", f"{micro['precision']:.3f}" if micro["precision"] is not None else "N/A")
        metrics[2].metric("Span recall", f"{micro['recall']:.3f}" if micro["recall"] is not None else "N/A")
        metrics[3].metric("Span F1", f"{micro['f1']:.3f}" if micro["f1"] is not None else "N/A")
        metrics[4].metric("Required types", f"{sum(benchmark_report['required_type_coverage'].values())}/9")
        st.dataframe(benchmark_report["rows"], width="stretch", hide_index=True)
