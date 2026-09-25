from __future__ import annotations

from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
from typing import Iterable

from .models import PIIRecord, PIIType, ReviewStatus


def _safe_ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _f1(precision: float | None, recall: float | None) -> float | None:
    if precision is None or recall is None or precision + recall == 0:
        return None
    return 2 * precision * recall / (precision + recall)


def _iou(first: Iterable[int] | None, second: Iterable[int] | None) -> float:
    if first is None or second is None:
        return 0.0
    ax1, ay1, ax2, ay2 = list(first)
    bx1, by1, bx2, by2 = list(second)
    intersection = max(0, min(ax2, bx2) - max(ax1, bx1)) * max(0, min(ay2, by2) - max(ay1, by1))
    union = max(0, ax2 - ax1) * max(0, ay2 - ay1) + max(0, bx2 - bx1) * max(0, by2 - by1) - intersection
    return intersection / union if union else 0.0


def _text_key(item: PIIRecord | dict) -> tuple:
    if isinstance(item, PIIRecord):
        return (item.pii_type.value, item.document_part, item.block_id, item.start_offset, item.end_offset)
    return (item["pii_type"], item["document_part"], item["block_id"], item["start_offset"], item["end_offset"])


def _match_predictions(predictions: list[PIIRecord], gold: list[dict], relaxed: bool = False) -> tuple[set[int], set[int]]:
    matched_predictions: set[int] = set()
    matched_gold: set[int] = set()
    for prediction_index, prediction in enumerate(predictions):
        best: tuple[float, int] | None = None
        for gold_index, truth in enumerate(gold):
            if gold_index in matched_gold or prediction.pii_type.value != truth["pii_type"]:
                continue
            truth_source = truth.get("source_kind", "native_text")
            prediction_is_image = prediction.source_kind in {"image", "ocr_text"} and prediction.media_name
            truth_is_image = truth_source in {"image", "ocr_text"} or truth.get("bounding_box") is not None
            if prediction_is_image or truth_is_image:
                if prediction.media_name != truth.get("media_name", truth.get("document_part")):
                    continue
                score = _iou(prediction.bounding_box, truth.get("bounding_box"))
                threshold = 0.3 if relaxed else 0.5
                if score >= threshold and (best is None or score > best[0]):
                    best = (score, gold_index)
                continue
            if prediction.document_part != truth["document_part"] or prediction.block_id != truth["block_id"]:
                continue
            if relaxed:
                overlap = max(0, min(prediction.end_offset, truth["end_offset"]) - max(prediction.start_offset, truth["start_offset"]))
                score = overlap / max(1, min(prediction.end_offset - prediction.start_offset, truth["end_offset"] - truth["start_offset"]))
                if score >= 0.5 and (best is None or score > best[0]):
                    best = (score, gold_index)
            elif _text_key(prediction) == _text_key(truth):
                best = (1.0, gold_index)
                break
        if best is not None:
            matched_predictions.add(prediction_index)
            matched_gold.add(best[1])
    return matched_predictions, matched_gold


def _character_accuracy(predictions: list[PIIRecord], gold: list[dict], manifest_path: Path | None) -> dict | str:
    if manifest_path is None or not manifest_path.exists():
        return "TBD until the full block manifest is available"
    lengths: dict[tuple[str, str], int] = {}
    total = 0
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = (row["document_part"], row["block_id"])
        lengths[key] = len(row.get("text", ""))
        total += lengths[key]
    predicted_masks: dict[tuple[str, str], set[int]] = defaultdict(set)
    gold_masks: dict[tuple[str, str], set[int]] = defaultdict(set)
    for item in predictions:
        if item.source_kind == "native_text":
            predicted_masks[(item.document_part, item.block_id)].update(range(item.start_offset, item.end_offset))
    for item in gold:
        if item.get("source_kind", "native_text") == "native_text":
            gold_masks[(item["document_part"], item["block_id"])].update(range(item["start_offset"], item["end_offset"]))
    tp = fp = fn = 0
    for key in set(lengths) | set(predicted_masks) | set(gold_masks):
        predicted = predicted_masks[key]
        truth = gold_masks[key]
        tp += len(predicted & truth)
        fp += len(predicted - truth)
        fn += len(truth - predicted)
    tn = max(0, total - tp - fp - fn)
    return {"tpchar": tp, "tnchar": tn, "fpchar": fp, "fnchar": fn, "accuracy": _safe_ratio(tp + tn, total)}


def evaluate(predictions: list[PIIRecord], gold_path: Path, manifest_path: Path | None = None) -> dict:
    if not gold_path.exists() or not gold_path.read_text(encoding="utf-8").strip():
        status_counts = Counter(item.review_status.value for item in predictions)
        type_counts = Counter(item.pii_type.value for item in predictions)
        unresolved_count = sum(
            item.review_status in {ReviewStatus.NEEDS_REVIEW, ReviewStatus.LOW_CONFIDENCE}
            for item in predictions
        )
        return {
            "status": "RELEASE_VALIDATION",
            "reason": "Independent full-corpus gold annotations are not available; accuracy metrics are not claimed.",
            "total_candidates": len(predictions),
            "unresolved_count": unresolved_count,
            "release_gate_passed": unresolved_count == 0,
            "status_counts": dict(sorted(status_counts.items())),
            "type_counts": dict(sorted(type_counts.items())),
        }
    gold = [json.loads(line) for line in gold_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    strict_predictions, strict_gold = _match_predictions(predictions, gold, relaxed=False)
    relaxed_predictions, relaxed_gold = _match_predictions(predictions, gold, relaxed=True)

    rows: list[dict] = []
    totals = Counter()
    for pii_type in [item.value for item in PIIType]:
        prediction_indexes = {index for index, item in enumerate(predictions) if item.pii_type.value == pii_type}
        gold_indexes = {index for index, item in enumerate(gold) if item["pii_type"] == pii_type}
        tp = len(prediction_indexes & strict_predictions)
        fp = len(prediction_indexes - strict_predictions)
        fn = len(gold_indexes - strict_gold)
        totals.update({"tp": tp, "fp": fp, "fn": fn})
        precision = _safe_ratio(tp, tp + fp)
        recall = _safe_ratio(tp, tp + fn)
        rows.append({
            "pii_type": pii_type, "support": len(gold_indexes), "tp": tp, "fp": fp, "fn": fn,
            "precision": precision, "recall": recall, "f1": _f1(precision, recall),
        })

    auto_indexes = {index for index, item in enumerate(predictions) if item.review_status == ReviewStatus.AUTO_APPROVED}
    confidence_bands: dict[str, dict] = {}
    for name, predicate in {
        "high": lambda value: value >= 0.85,
        "medium": lambda value: 0.60 <= value < 0.85,
        "low": lambda value: value < 0.60,
    }.items():
        indexes = {index for index, item in enumerate(predictions) if predicate(item.final_confidence)}
        tp = len(indexes & strict_predictions)
        confidence_bands[name] = {"predictions": len(indexes), "tp": tp, "precision": _safe_ratio(tp, len(indexes))}

    detector_contribution = Counter()
    for index in strict_predictions:
        for item in predictions[index].evidence:
            detector_contribution[item.source.value] += 1
    human_actions = Counter(
        evidence.recognizer_name.removeprefix("human_").upper()
        for record in predictions for evidence in record.evidence
        if evidence.recognizer_name.startswith("human_")
    )
    image_predictions = [item for item in predictions if item.source_kind in {"image", "ocr_text"}]
    image_gold = [item for item in gold if item.get("source_kind") in {"image", "ocr_text"} or item.get("bounding_box") is not None]
    micro_precision = _safe_ratio(totals["tp"], totals["tp"] + totals["fp"])
    micro_recall = _safe_ratio(totals["tp"], totals["tp"] + totals["fn"])
    relaxed_precision = _safe_ratio(len(relaxed_predictions), len(predictions))
    relaxed_recall = _safe_ratio(len(relaxed_gold), len(gold))
    return {
        "status": "COMPLETE",
        "rows": rows,
        "micro": {
            "tp": totals["tp"], "fp": totals["fp"], "fn": totals["fn"],
            "precision": micro_precision, "recall": micro_recall, "f1": _f1(micro_precision, micro_recall),
        },
        "relaxed": {
            "tp": len(relaxed_predictions), "fp": len(predictions) - len(relaxed_predictions),
            "fn": len(gold) - len(relaxed_gold), "precision": relaxed_precision,
            "recall": relaxed_recall, "f1": _f1(relaxed_precision, relaxed_recall),
        },
        "automatic_replacement_precision": _safe_ratio(len(auto_indexes & strict_predictions), len(auto_indexes)),
        "review_workload": _safe_ratio(
            sum(item.review_status in {ReviewStatus.NEEDS_REVIEW, ReviewStatus.LOW_CONFIDENCE} for item in predictions),
            len(predictions),
        ),
        "confidence_bands": confidence_bands,
        "detector_source_contribution": dict(sorted(detector_contribution.items())),
        "human_review_actions": dict(sorted(human_actions.items())),
        "image_replacement_coverage": _safe_ratio(
            len({item.media_name for item in image_predictions if item.media_name}),
            len({item.get("media_name", item.get("document_part")) for item in image_gold}),
        ),
        "character_accuracy": _character_accuracy(predictions, gold, manifest_path),
    }


def _format_metric(value: float | None) -> str:
    return "N/A" if value is None else f"{value:.4f}"


def write_evaluation(
    report: dict,
    markdown_path: Path,
    csv_path: Path,
    *,
    title: str = "PII Redaction Evaluation Report",
    scope_note: str | None = None,
) -> None:
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    if report["status"] == "RELEASE_VALIDATION":
        rows = [
            {"section": "release", "pii_type": "ALL", "metric": "total_candidates", "value": report["total_candidates"], "notes": "All centralized detections"},
            {"section": "release", "pii_type": "ALL", "metric": "unresolved_review_items", "value": report["unresolved_count"], "notes": "Must be zero for final release"},
            {"section": "release", "pii_type": "ALL", "metric": "release_gate_passed", "value": str(report["release_gate_passed"]).lower(), "notes": "Review-completion gate"},
        ]
        rows.extend(
            {"section": "decision_status", "pii_type": "ALL", "metric": key.casefold(), "value": value, "notes": "Reviewed candidate count"}
            for key, value in report["status_counts"].items()
        )
        rows.extend(
            {"section": "candidate_type", "pii_type": key, "metric": "candidate_count", "value": value, "notes": "Detected candidate count"}
            for key, value in report["type_counts"].items()
        )
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["section", "pii_type", "metric", "value", "notes"])
            writer.writeheader()
            writer.writerows(rows)
        lines = [
            "# PII Redaction Evaluation Report", "", "## Release validation", "",
            f"Review gate: **{'PASS' if report['release_gate_passed'] else 'FAIL'}**", "",
            f"- Total candidates: {report['total_candidates']}",
            f"- Unresolved review items: {report['unresolved_count']}",
            "", "## Review outcomes", "", "| Status | Count |", "|---|---:|",
        ]
        lines.extend(f"| {key} | {value} |" for key, value in report["status_counts"].items())
        lines.extend(["", "## Candidates by type", "", "| Type | Count |", "|---|---:|"])
        lines.extend(f"| {key} | {value} |" for key, value in report["type_counts"].items())
        lines.extend([
            "", "## Accuracy scope", "",
            report["reason"],
            "The CSV reports release coverage and adjudication counts. Precision, recall, and F1 remain unavailable rather than being inferred from the same detections used to create the output.",
        ])
        markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return
    if report["status"] != "COMPLETE":
        markdown_path.write_text(
            f"# {title}\n\n"
            "## Status\n\n"
            f"Metrics are **TBD**. {report['reason']}\n\n"
            "The evaluator is implemented for exact-span text matching, relaxed overlap, image bounding-box IoU, "
            "character accuracy, automatic-replacement precision, confidence bands, detector contribution, "
            "review workload, and image coverage. It will run only after the complete prospectus is manually annotated.\n",
            encoding="utf-8",
        )
        csv_path.write_text("pii_type,support,tp,fp,fn,precision,recall,f1\n", encoding="utf-8")
        return
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pii_type", "support", "tp", "fp", "fn", "precision", "recall", "f1"])
        writer.writeheader()
        writer.writerows(report["rows"])
    lines = [f"# {title}", ""]
    if scope_note:
        lines.extend([scope_note, ""])
    lines.extend([
        "## Strict exact-span and image IoU results", "",
        "| Type | Support | TP | FP | FN | Precision | Recall | F1 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for row in report["rows"]:
        lines.append(
            f"| {row['pii_type']} | {row['support']} | {row['tp']} | {row['fp']} | {row['fn']} | "
            f"{_format_metric(row['precision'])} | {_format_metric(row['recall'])} | {_format_metric(row['f1'])} |"
        )
    micro = report["micro"]
    relaxed = report["relaxed"]
    lines.extend([
        "", "## Aggregate results", "",
        f"- Strict micro precision / recall / F1: {_format_metric(micro['precision'])} / {_format_metric(micro['recall'])} / {_format_metric(micro['f1'])}",
        f"- Relaxed precision / recall / F1: {_format_metric(relaxed['precision'])} / {_format_metric(relaxed['recall'])} / {_format_metric(relaxed['f1'])}",
        f"- Automatic-replacement precision: {_format_metric(report['automatic_replacement_precision'])}",
        f"- Review workload: {_format_metric(report['review_workload'])}",
        f"- Image replacement coverage: {_format_metric(report['image_replacement_coverage'])}",
        f"- Character accuracy: {json.dumps(report['character_accuracy'], ensure_ascii=False)}",
        "", "## Confidence bands", "",
        "| Band | Predictions | TP | Precision |", "|---|---:|---:|---:|",
    ])
    if "negative_controls" in report:
        controls = report["negative_controls"]
        lines.extend([
            "", "## Hard negative controls", "",
            f"- Blocks: {controls['blocks']}",
            f"- True-negative blocks: {controls['true_negative_blocks']}",
            f"- False-positive blocks: {controls['false_positive_blocks']}",
            f"- False-positive entities: {controls['false_positive_entities']}",
        ])
    for band, values in report["confidence_bands"].items():
        lines.append(f"| {band} | {values['predictions']} | {values['tp']} | {_format_metric(values['precision'])} |")
    lines.extend([
        "", "## Detector contribution", "",
        json.dumps(report["detector_source_contribution"], ensure_ascii=False, sort_keys=True),
        "", "## Human review actions", "",
        json.dumps(report["human_review_actions"], ensure_ascii=False, sort_keys=True),
    ])
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
