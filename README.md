# Full Dataset PII Pseudonymizer

This project processes the complete supplied `Red Herring Prospectus.docx` locally. It detects structured and contextual PII in native DOCX text and embedded media, records explainable confidence evidence, generates a mandatory review queue, preserves related identities, and produces deterministic synthetic replacements without changing the source file.

## Data handling

- Document content is never sent to an external API.
- Raw detections, mappings, annotations, and review decisions are written only under `data/private/`, which is excluded from version control and from the submission bundle.
- Shareable reports contain record identifiers and keyed fingerprints rather than original values.
- All embedded media is replaced in this dataset because the supplied assets contain identity documents, commercial logos, or machine-readable content.

## Setup

Use Python 3.12 and install the versions in `requirements.in`. Install Tesseract OCR and configure its path in `config.toml`. The implementation uses Presidio pattern recognizers and one spaCy `en_core_web_md` NER pass.

Set the deterministic secret in the environment before running:

```powershell
$env:PII_REDACTION_SEED = "store-this-secret-outside-the-project"
```

## Commands

```powershell
python -m pii_redactor --config config.toml inspect
python -m pii_redactor --config config.toml run-all
python -m pii_redactor --config config.toml review export
python -m pii_redactor --config config.toml review apply
python -m pii_redactor --config config.toml verify
```

Add `src` to `PYTHONPATH` when the package has not been installed:

```powershell
$env:PYTHONPATH = "$PWD\src"
```

## Confidence and review

- Scores at or above `0.85` are automatically accepted.
- Scores from `0.60` through `0.849999` require review.
- Lower-scoring candidates enter the low-confidence inspection queue.
- A safe review draft is generated while unresolved items remain. The submission-ready filename is withheld until every queued record has a decision in `data/private/review_decisions.jsonl`.

Supported decisions are `APPROVE`, `REJECT_AS_NON_PII`, `RETYPE`, `ADJUST_SPAN`, `LINK_IDENTITY`, `UNLINK_IDENTITY`, `FORCE_MEDIA_REPLACEMENT`, and `CLEAR_MEDIA`.

## Output modes

- `synthetic` is the default and generates linked, deterministic identities.
- `mask` emits stable typed tokens.
- `partial` retains limited suffix information for supported identifiers and falls back to complete masking for unsafe types.

## Evaluation

`data/private/full_dataset_annotation_manifest.private.jsonl` contains every extracted source block for full-corpus annotation. Reviewed entity annotations belong in `data/private/gold_annotations.jsonl`. Until that file is complete, `EVALUATION_REPORT.md` correctly reports all metrics as `TBD`; the implementation does not invent results.

Exact-span per-type and micro precision, recall, and F1 are calculated after the gold corpus is frozen. Character accuracy remains unavailable until the gold file includes character-level masks.

## Known tradeoffs

NER can confuse public institutions, commercial entities, people, and document headings. Address spans can overlap contact details, and OCR may misread stylized logos or degraded identity documents. The mandatory review gate, checksum validation, negative contexts, full-media replacement, and package-wide residual checks are used to contain those risks.

## Current supplied-dataset run

The implemented full-dataset run extracted 4,254 text blocks, evaluated all eight embedded media assets, and produced 2,298 centralized candidate records. It auto-approved 369 high-confidence records and exported 1,929 records for mandatory review. Because those decisions and the independent full-corpus gold annotation are not complete, the pipeline intentionally produced `Red Herring Prospectus - Review Draft.docx`; it did not create the submission-ready final filename or invent evaluation metrics.

The review draft reopened successfully, all approved replacement values were found in their output blocks, all eight media assets were replaced, and all 127 rendered pages were visually inspected. See `reports/summary_report.json` and `reports/visual_qa.json` for the machine-readable run status.
