# DOCX PII Redaction Studio

A local Python application that detects personally identifiable information in Word documents and replaces approved personal data with deterministic synthetic alternatives. It was built for the supplied KSH International Limited Red Herring Prospectus (RHP), where legitimate corporate facts must remain unchanged.

The application does not claim that every possible PII value is detected. It provides measurable controlled-benchmark evidence, an explicit review/policy gate, and post-save QA so the remaining risk is visible.

## Problem and policy

The assignment requires a redacted/pseudonymized DOCX and support for nine categories:

`PERSON`, `EMAIL`, `PHONE`, `COMPANY`, `ADDRESS`, `SSN`, `CREDIT_CARD`, `DOB`, and `IPV4`.

Detection is separate from the release decision:

```text
DOCX/OCR → detection evidence → confidence/overlap merge
         → REDACT | PROTECT | REVIEW | IGNORE
         → deterministic replacement → DOCX/media QA → reports
```

For the real RHP, `COMPANY`, `CIN`, `GSTIN`, and `IFSC` default to **PROTECT**. Thus `KSH International Limited` is detected and reported but remains unchanged. Personal PII such as a person's name, email, phone or address is pseudonymized after approval. Strict benchmark mode still measures company detection independently of this production policy.

## Architecture

The implementation remains modular:

- `recognizers.py`: Presidio patterns, spaCy NER, context rules, `phonenumbers`, Luhn, IPv4 and SSN validation.
- `ensemble.py`: evidence merging, confidence bands and overlap resolution.
- `policy.py`: REDACT/PROTECT/REVIEW/IGNORE decisions, independent of detection.
- `relationships.py` and `pseudonyms.py`: stable identities and HMAC-derived fake alternatives.
- `docx_io.py`: direct OOXML traversal and run-preserving span replacement.
- `media.py`: local OCR, QR inspection, sensitive-media placeholders and media hashes.
- `review.py`: source-hash-bound review decisions and unresolved-item gating.
- `qa.py`: DOCX ZIP/reopen, structural, replacement, residual and media checks.
- `evaluation.py` and `benchmark.py`: generated exact-span and block-classification metrics.
- `pipeline.py`, `cli.py`, and `app.py`: one shared engine for CLI and Streamlit.

Optional Indian extensions (`PAN`, `AADHAAR`, `PASSPORT`, `GSTIN`, `CIN`, `IFSC`) remain available, but they are not counted as substitutes for the assignment's nine required types.

## Detection and replacement

Structured patterns are validated where possible: cards must pass Luhn, IPv4 values must parse, SSNs reject structurally invalid groups, and phone values are parsed with `phonenumbers`. Ordinary dates are not DOB unless birth context is present. Addresses require address context plus postal/structural evidence. spaCy supplies PERSON and organization candidates, while known public authorities and non-company labels are filtered.

Synthetic mode is the default:

| Type | Replacement behavior |
|---|---|
| PERSON | synthetic full name |
| EMAIL | linked `example.test` address |
| PHONE | synthetic Indian-format number |
| ADDRESS | synthetic test address |
| COMPANY | synthetic company only when policy explicitly says REDACT |
| DOB | synthetic date in the original style |
| IPV4 | IANA TEST-NET-2 (`198.51.100.0/24`) address |
| SSN | intentionally non-issued `000-00-xxxx` test value |
| CREDIT_CARD | Luhn-valid test-style card preserving separators |

An HMAC seed makes the mapping deterministic without putting original values in public reports. The same normalized value/identity receives the same replacement in a run. Mask and partial modes are available, but are not the assignment default.

## DOCX and media safety

Text traversal includes body paragraphs, arbitrary nested tables, headers, footers, footnotes, endnotes and comments when those parts exist. Replacements operate on OOXML text nodes so multi-run values can be changed without flattening the paragraph. External relationship targets are patched only when they contain an approved value; internal package paths are not altered.

Media is extracted, hashed and inspected locally. The default replaces only media with structured PII, identity-document terms or decoded QR evidence. The UI's explicitly labeled high-security option replaces every embedded image, including harmless logos. Tesseract is optional; without it, native DOCX processing still works and OCR evidence is unavailable.

Post-save QA verifies that the output is a valid ZIP/DOCX, can be reopened by `python-docx`, preserves structural element counts, contains each expected replacement, changes selected media, and has no approved original remaining in its original processed block. This is strong release evidence, not proof that an undetected value cannot exist.

## Installation (Windows PowerShell)

Python 3.12 is the verified runtime. The lock file is authoritative.

```powershell
git clone https://github.com/saumyasaini11/redact-scalarai.git
cd redact-scalarai
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
```

Or let the Python UI launcher create/install the environment:

```powershell
python run.py --setup
```

For OCR, install Tesseract and either place `tesseract` on `PATH` or set:

```powershell
$env:TESSERACT_CMD = "D:\Tools\Tesseract-OCR\tesseract.exe"
```

No source-code edit is required. `config.toml` can also specify a portable deployment path, but is blank by default.

## Run the CLI

Place the supplied document at `data/input/Red Herring Prospectus (1).docx`, then:

```powershell
$env:PYTHONPATH = "$PWD\src"
$env:PII_REDACTION_SEED = "replace-with-a-private-random-secret"
.\.venv\Scripts\python.exe -m pii_redactor.cli inspect
.\.venv\Scripts\python.exe -m pii_redactor.cli run-all
```

`run-all` produces a review draft when review-policy items remain. Resolve them in the UI, or use the explicit conservative policy finalizer:

```powershell
.\.venv\Scripts\python.exe -m pii_redactor.cli review finalize
```

That command protects corporate facts and redacts remaining personal candidates. It is a privacy-first policy action, not human annotation and not evidence of full-document precision.

Final output: `data/output/Red Herring Prospectus - Pseudonymized.docx`.

Build the shareable source/evidence/output archive (it excludes the original DOCX and private mappings):

```powershell
.\.venv\Scripts\python.exe scripts\build_submission.py
```

Archive: `dist/scalarai-pii-redaction-submission.zip`.

## Run the Streamlit UI

```powershell
python run.py
```

The UI exposes the requested flow as:

1. Upload
2. Analyze
3. View detection summary
4. Review policy decisions
5. Redact
6. Verify/evaluate
7. Download

It shows detected counts, protected/redacted/ignored/review counts, QA status and the generated benchmark. Synthetic replacements, company protection and sensitive-media-only handling are the defaults.

## Tests and benchmark

```powershell
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pii_redactor.cli benchmark
```

The frozen manually defined gold benchmark contains one positive exact-span fixture for every required type plus twelve hard-negative blocks (ordinary dates, amounts, order/page numbers, legal terms, invalid IP/card lookalikes and identifiers).

| Metric | Unit | Result |
|---|---|---:|
| TP / FP / FN | exact entity/span | 9 / 0 / 0 |
| Precision | exact entity/span | 1.0000 |
| Recall | exact entity/span | 1.0000 |
| F1 | exact entity/span | 1.0000 |
| TP / TN / FP / FN | binary text block | 9 / 12 / 0 / 0 |
| Accuracy | binary text block | 1.0000 |
| Character accuracy | character coverage (additional) | 1.0000 |
| Required types detected | controlled fixtures | 9 / 9 |

These values are generated by code in the [final evaluation report](docs/EVALUATION_REPORT.md) and [benchmark report](reports/benchmark/required_types_evaluation.md). They show behavior on 21 deliberately small controlled blocks; they are not full-document RHP precision or recall.

## Final RHP QA run

The final clean policy run produced:

| Item | Result |
|---|---:|
| Candidates | 2,233 |
| Redacted/pseudonymized by policy | 341 |
| Protected corporate facts | 1,892 |
| Unresolved policy-review items | 0 |
| Sensitive media replaced | 1 / 8 |
| Replacement application failures | 0 |
| Residual approved originals in processed blocks | 0 |
| Automated QA findings | 0 |
| DOCX release gate | PASS |

`KSH International Limited` remains in the output; the verified contact name `Sarthak Malvadkar` does not. See [final evaluation](docs/EVALUATION_REPORT.md), [RHP QA](docs/RHP_QA_REPORT.md), [tracker](docs/REDACTION_TRACKER.md), and `reports/summary_report.json`. No full-document precision, recall or accuracy is reported because the RHP does not have full-document gold annotations.

## Evaluation definitions

- Exact entity/span precision: `TP / (TP + FP)`.
- Exact entity/span recall: `TP / (TP + FN)`.
- F1: `2 × precision × recall / (precision + recall)`.
- Block classification accuracy: `(TP + TN) / (TP + TN + FP + FN)`.

True negatives use a finite text-block manifest. Character accuracy is reported separately and never called classification accuracy. Undefined divisions are written as `N/A`, not zero. Labels are described as a controlled/frozen manually defined gold benchmark; there was no independent annotator.

## False positives, false negatives and limitations

- spaCy can label legal headings, short abbreviations or schemes as people/organizations. Company protection prevents these organization candidates from changing real corporate facts, while ambiguous personal candidates still require review or conservative redaction.
- Names and addresses with unusual OCR, spelling or fragmented drawing/text-box layouts can be missed.
- Text boxes stored outside supported OOXML text parts may not be extracted.
- OCR depends on local Tesseract quality. QR detection and full-image placeholder replacement do not selectively edit pixels inside an image.
- Sensitive-media-only mode deliberately preserves harmless graphics; high-security mode trades layout semantics for lower disclosure risk.
- The controlled benchmark is intentionally small. A larger independently annotated RHP sample would be the next meaningful evaluation improvement.
- Synthetic values are test data, not guaranteed deliverable phone/address identities. Reserved domains/ranges are used where available.

## Security and repository hygiene

Raw originals, review decisions, identity mappings, uploads and outputs are gitignored. Shareable logs contain keyed fingerprints instead of raw values. Upload validation limits size, uncompressed size, package members, encryption and unsafe paths.

The current tree no longer tracks `.venv`, the supplied source DOCX or per-record generated logs. Earlier Git commits did contain `.venv` and the source DOCX; removing those historical blobs requires a coordinated `git filter-repo` rewrite and force-push. That destructive history operation is intentionally not performed automatically.

The final redacted DOCX is a separate assignment artifact under `data/output/`; it is not committed as source code.

## Reference comparison

The evidence-based A–AB comparison is in [docs/COMPARISON.md](docs/COMPARISON.md). The reference has a simpler one-click presentation, while this project retains the stronger policy, deterministic pseudonymization, validation, OCR/media, review, QA and executable evaluation design.
