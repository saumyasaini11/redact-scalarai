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
    read_jsonl,
    finalize_pending_privacy_first,
    save_review_decisions,
)
from pii_redactor.benchmark import run_required_type_benchmark
from pii_redactor.pipeline import run_pipeline


st.set_page_config(page_title="DOCX PII Redactor", page_icon="🔐", layout="wide")
st.title("DOCX PII Redactor")
st.caption("Local, confidence-aware pseudonymization with review gating, media replacement, QA, and measured evaluation")

with st.sidebar:
    st.header("Redaction policy")
    mode_label = st.selectbox(
        "Replacement mode",
        ["Synthetic pseudonyms", "Mask (obvious redaction)", "Partial masking"],
        help="Synthetic mode is the assignment default and substitutes deterministic fake alternatives.",
    )
    mode = {
        "Mask (obvious redaction)": "mask",
        "Synthetic pseudonyms": "synthetic",
        "Partial masking": "partial",
    }[mode_label]
    high_threshold = st.slider("Automatic approval threshold", 0.70, 0.99, 0.85, 0.01)
    medium_threshold = st.slider("Review threshold", 0.30, high_threshold, 0.60, 0.01)
    default_region = st.text_input("Phone region", "IN", max_chars=2).upper()
    replace_all_media = st.checkbox(
        "High-security mode: replace all embedded media",
        value=False,
        help="Off replaces only media with PII/identity/QR evidence. On also replaces harmless logos and graphics.",
    )
    company_scope = st.selectbox(
        "Corporate entity policy",
        ["protect", "review", "redact"],
        help="Protect preserves company names and public corporate identifiers while still detecting and reporting them.",
    )
    seed = st.text_input(
        "Private deterministic seed",
        value=st.session_state.setdefault("seed", secrets.token_urlsafe(24)),
        type="password",
        help="The seed stays in this process and makes replacements consistent across repeated identities.",
    )

upload_tab, review_tab, evaluation_tab = st.tabs([
    "Steps 1–3 · Upload, analyze, summary",
    "Steps 4–5 · Review policy, redact",
    "Steps 6–7 · Verify, evaluate, download",
])

with upload_tab:
    uploaded = st.file_uploader("Upload a Word document", type=["docx"])
    gold_upload = st.file_uploader(
        "Optional gold annotations",
        type=["jsonl"],
        help="Provide exact spans to calculate document-specific precision, recall, and F1.",
    )
    if uploaded and st.button("Analyze and create review draft", type="primary"):
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
            with st.spinner("Scanning native text, relationships, headers, footers, comments, and embedded media..."):
                result = run_pipeline(app_run.settings)
            st.session_state["app_run"] = app_run
            st.session_state["pipeline_result"] = result
            if result.release_ready:
                st.success(f"Redaction complete: {result.record_count} candidates processed and QA passed.")
            else:
                st.warning(
                    f"A review draft was created: {result.unresolved_count} decisions remain and "
                    f"{len(result.qa_errors)} QA findings need attention."
                )
        except Exception as exc:
            st.exception(exc)

    app_run = st.session_state.get("app_run")
    result = st.session_state.get("pipeline_result")
    if app_run and result:
        summary_path = app_run.settings.reports_dir / "summary_report.json"
        summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
        cols = st.columns(4)
        cols[0].metric("Candidates", summary.get("total_candidates", result.record_count))
        cols[1].metric("Needs review", result.unresolved_count)
        cols[2].metric("Media replaced", f"{summary.get('media_replaced', 0)}/{summary.get('media_total', 0)}")
        cols[3].metric("QA errors", len(result.qa_errors))
        policy_cols = st.columns(4)
        policy_cols[0].metric("Redacted", summary.get("redacted_entities", 0))
        policy_cols[1].metric("Protected", summary.get("protected_entities", 0))
        policy_cols[2].metric("Ignored", summary.get("ignored_entities", 0))
        policy_cols[3].metric("Policy review", summary.get("policy_review_required", 0))
        if summary.get("entities_by_type"):
            st.subheader("Detected PII summary")
            st.dataframe(
                [{"PII type": key, "Candidates": value} for key, value in summary["entities_by_type"].items()],
                width="stretch",
                hide_index=True,
            )
        if result.release_ready:
            st.success("The final redacted document is ready to download from the review tab.")
        else:
            st.warning("This is only a review draft. Do not treat it as a fully redacted document.")

with review_tab:
    app_run: AppRun | None = st.session_state.get("app_run")
    if not app_run:
        st.info("Upload and analyze a DOCX first.")
    else:
        queue_path = app_run.settings.private_dir / "review_queue.jsonl"
        queue = read_jsonl(queue_path)
        edited = None
        source_hash = ""
        if not queue:
            st.success("No unresolved records remain. The document can be finalized.")
        else:
            source_hash = queue[0]["source_hash"]
            available_types = sorted({item["pii_type"] for item in queue})
            selected_types = st.multiselect("Filter review queue by type", available_types, default=available_types)
            visible_queue = [item for item in queue if item["pii_type"] in selected_types]
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
            } for item in visible_queue]
            st.warning("Review values are displayed locally because a human decision is required. They are never included in the shareable bundle.")
            if st.button(f"Privacy-first finalize {len(queue)} pending items"):
                try:
                    finalize_pending_privacy_first(
                        app_run.settings.private_dir / "review_decisions.jsonl",
                        queue,
                    )
                    with st.spinner("Applying all redactions and running package-wide QA..."):
                        result = run_pipeline(app_run.settings)
                    st.session_state["pipeline_result"] = result
                    st.rerun()
                except Exception as exc:
                    st.exception(exc)
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
                    app_run.settings.private_dir / "review_decisions.jsonl",
                    edited,
                    source_hash,
                )
                st.success(f"Saved {saved} decisions.")

        if st.button("Apply decisions and regenerate", type="primary"):
            try:
                if edited is not None:
                    save_review_decisions(
                        app_run.settings.private_dir / "review_decisions.jsonl",
                        edited,
                        source_hash,
                    )
                with st.spinner("Regenerating the DOCX and running package-wide QA..."):
                    result = run_pipeline(app_run.settings)
                st.session_state["pipeline_result"] = result
                if result.release_ready:
                    st.success("Final document passed review gating and QA.")
                else:
                    st.warning(f"A review draft was regenerated; {result.unresolved_count} decisions remain.")
            except Exception as exc:
                st.exception(exc)

        result = st.session_state.get("pipeline_result")
        if result and result.output_path.exists():
            mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            download_label = "Download final redacted DOCX" if result.release_ready else "Download review draft DOCX"
            st.download_button(download_label, result.output_path.read_bytes(), result.output_path.name, mime)
            st.download_button(
                "Download sanitized submission bundle",
                build_download_bundle(app_run, result.output_path),
                f"pii-redaction-{app_run.run_id}.zip",
                "application/zip",
            )
            evaluation_path = app_run.root / "docs" / "RHP_QA_REPORT.md"
            if evaluation_path.exists():
                st.download_button(
                    "Download RHP_QA_REPORT.md",
                    evaluation_path.read_bytes(),
                    "RHP_QA_REPORT.md",
                    "text/markdown",
                )
            if result.qa_errors:
                st.error("QA findings: " + "; ".join(result.qa_errors))

with evaluation_tab:
    st.subheader("Verification and downloads")
    current_result = st.session_state.get("pipeline_result")
    current_run = st.session_state.get("app_run")
    if current_result:
        if current_result.release_ready:
            st.success("Review gate and automated DOCX QA passed.")
        else:
            st.warning(
                f"Not release-ready: {current_result.unresolved_count} review items and "
                f"{len(current_result.qa_errors)} QA findings remain."
            )
    if current_run and current_result and current_result.output_path.exists():
        st.download_button(
            "Download current DOCX",
            current_result.output_path.read_bytes(),
            current_result.output_path.name,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    st.subheader("Measured nine-type benchmark")
    st.write(
        "This frozen corpus measures exact-span precision, recall, and F1 for PERSON, EMAIL, PHONE, "
        "COMPANY, ADDRESS, SSN, CREDIT_CARD, DOB, and IPV4. It is reported separately from an "
        "uploaded document unless gold annotations are supplied."
    )
    if st.button("Run required-type benchmark"):
        try:
            with st.spinner("Running the production detector against frozen labels..."):
                report = run_required_type_benchmark(PROJECT_ROOT / "reports" / "benchmark")
            st.session_state["benchmark_report"] = report
        except Exception as exc:
            st.exception(exc)
    report = st.session_state.get("benchmark_report")
    if report:
        micro = report["micro"]
        classification = report["block_classification"]
        cols = st.columns(5)
        cols[0].metric("Block accuracy", f"{classification['accuracy']:.3f}")
        cols[1].metric("Span precision", f"{micro['precision']:.3f}" if micro["precision"] is not None else "N/A")
        cols[2].metric("Span recall", f"{micro['recall']:.3f}" if micro["recall"] is not None else "N/A")
        cols[3].metric("Span F1", f"{micro['f1']:.3f}" if micro["f1"] is not None else "N/A")
        cols[4].metric("Required types", f"{sum(report['required_type_coverage'].values())}/9")
        st.dataframe(report["rows"], width="stretch", hide_index=True)

    final_evaluation_path = PROJECT_ROOT / "docs" / "EVALUATION_REPORT.md"
    if final_evaluation_path.exists():
        st.download_button(
            "Download EVALUATION_REPORT.md",
            final_evaluation_path.read_bytes(),
            "EVALUATION_REPORT.md",
            "text/markdown",
        )

    app_run = st.session_state.get("app_run")
    if app_run:
        evaluation_path = app_run.root / "docs" / "RHP_QA_REPORT.md"
        if evaluation_path.exists():
            st.subheader("Uploaded document evaluation")
            st.markdown(evaluation_path.read_text(encoding="utf-8"))
