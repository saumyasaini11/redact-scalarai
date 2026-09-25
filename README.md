# DOCX PII Redaction Studio

A local, privacy-first tool for pseudonymizing sensitive personal information in Microsoft Word documents. Upload a `.docx`, let the tool find and replace every piece of PII with realistic synthetic data, review anything it's unsure about, and download a clean, auditable output — all without sending a single byte to an external server.

Built for the Indian regulatory context (PAN, Aadhaar, GSTIN, CIN, IFSC, etc.) while also covering universal types like email, phone, credit card, and IP address.

---

## How it works

At a high level, the pipeline does five things:

1. **Detects PII** — runs regex/Presidio pattern recognizers, a spaCy NER pass, checksum validators (Luhn, Verhoeff, phonenumbers), and OCR on embedded images
2. **Scores confidence** — merges evidence from all detectors into a single confidence score per candidate
3. **Routes for review** — high-confidence hits are auto-approved; borderline ones go to a human review queue; anything below the lower threshold is flagged for inspection
4. **Replaces values** — approved candidates get a deterministic synthetic replacement (or a stable mask/partial token, depending on your mode). The same original value always produces the same replacement within a run.
5. **Validates output** — checksums the output file, scans for residual originals in the XML, and confirms all embedded media was replaced

Nothing leaves your machine. Raw detections, identity mappings, and review decisions are written to `data/private/` which is gitignored and never included in the shareable download bundle.

---

## Benchmark results

The tool was evaluated against a frozen, independently labeled benchmark covering 9 PII types. These are real measured numbers — not estimates.

| Metric | Score |
|---|---|
| **Precision** | 0.9000 |
| **Recall** | 1.0000 |
| **F1** | 0.9474 |
| **Character accuracy** | 0.9897 |
| **Types detected** | 9 / 9 |

Types covered: `PERSON`, `EMAIL`, `PHONE`, `ADDRESS`, `COMPANY`, `DOB`, `PAN`, `AADHAAR`, `CREDIT_CARD`

Full per-type breakdown is in [`reports/benchmark/required_types_evaluation.md`](reports/benchmark/required_types_evaluation.md).

> **Note:** These numbers are for the controlled benchmark only. Full-corpus precision and recall for the prospectus are not claimed until independent gold annotations are provided.

---

## Results on the supplied prospectus

The tool was run end-to-end on a 127-page Red Herring Prospectus. Here's what happened:

| Stage | Count |
|---|---|
| Text blocks extracted | 4,254 |
| Embedded media assets | 8 / 8 replaced |
| Total PII candidates found | 2,316 |
| Auto-approved (confidence ≥ 0.85) | 289 |
| Approved during human review | 281 |
| Rejected as false positives | 1,746 |
| Unresolved items remaining | **0** |

The final output (`data/output/Red Herring Prospectus - Pseudonymized.docx`) passed all QA checks: no residual approved originals in the DOCX XML, all 8 media assets replaced, and the document re-opened correctly across 127 pages.

---

## Project structure

```
.
├── app.py                  # Streamlit web app — the main UI
├── config.toml             # Configuration: paths, thresholds, tool settings
├── pytest.ini              # Test configuration
├── requirements.in         # Python dependencies
│
├── src/pii_redactor/       # Core Python package
│   ├── pipeline.py         # Orchestrates the full redaction run
│   ├── recognizers.py      # All PII detectors (regex, NER, checksums)
│   ├── ensemble.py         # Merges and scores multi-source evidence
│   ├── models.py           # Data classes: PIIRecord, Evidence, etc.
│   ├── pseudonyms.py       # Deterministic synthetic replacement engine
│   ├── review.py           # Review queue read/write
│   ├── policy.py           # REDACT / PROTECT / IGNORE policy engine
│   ├── docx_io.py          # DOCX reading, patching, and saving
│   ├── media.py            # Image OCR and media replacement
│   ├── qa.py               # Output validation and residual scanning
│   ├── evaluation.py       # Precision/recall/F1 computation
│   ├── benchmark.py        # Frozen 9-type benchmark runner
│   ├── reporting.py        # Summary and audit log generation
│   ├── relationships.py    # Identity linking across records
│   ├── app_service.py      # Streamlit session helpers and download bundle
│   ├── config.py           # Settings dataclass and TOML loader
│   └── cli.py              # CLI command definitions
│
├── tests/                  # Pytest test suite (8 modules)
├── scripts/                # run_app.ps1 and utility scripts
├── docs/                   # COMPARISON.md, EVALUATION_REPORT.md, REDACTION_TRACKER.md
├── data/
│   ├── input/              # Source DOCX files
│   ├── output/             # Pseudonymized and draft output files
│   ├── private/            # Raw PII data — gitignored, never shared
│   └── app_runs/           # Per-upload Streamlit session workspaces
├── reports/
│   ├── benchmark/          # Frozen benchmark labels and results
│   └── ...                 # Sanitized audit logs and summary reports
└── dist/                   # Release ZIP archives
```

---

## Setup

**Requirements:** Python 3.12, [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki)

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.in

# 3. Set your private deterministic seed (keep this outside the project)
$env:PII_REDACTION_SEED = "your-secret-seed-here"
```

The seed is what makes replacements consistent — the same original value will always produce the same synthetic replacement within a run. Store it somewhere safe; changing it changes all output values.

Make sure Tesseract is installed and its path is set in `config.toml` under `[tools]`:

```toml
[tools]
tesseract_cmd = "C:/Program Files/Tesseract-OCR/tesseract.exe"
```

---

## Running the app

**Streamlit UI (recommended):**

```powershell
streamlit run app.py
```

Or use the bundled script which handles the venv automatically:

```powershell
.\scripts\run_app.ps1
```

The UI walks you through three steps:
1. **Upload & Analyze** — upload a DOCX, choose your policy settings, and run detection
2. **Review & Redact** — go through the flagged items, approve or reject each one, then regenerate the output
3. **Verify & Evaluate** — run the benchmark, download the sanitized report bundle

**CLI (for scripted runs):**

```powershell
# Set the source path first
$env:PYTHONPATH = "$PWD\src"

python -m pii_redactor --config config.toml inspect        # List what was found
python -m pii_redactor --config config.toml run-all        # Full redaction run
python -m pii_redactor --config config.toml benchmark      # Run the benchmark
python -m pii_redactor --config config.toml review export  # Export the review queue
python -m pii_redactor --config config.toml review apply   # Apply saved decisions
python -m pii_redactor --config config.toml verify         # QA the output
```

---

## Confidence thresholds and the review queue

Every detected candidate gets a confidence score between 0 and 1. Here's how they're routed:

| Score range | What happens |
|---|---|
| **≥ 0.85** | Auto-approved and redacted immediately |
| **0.60 – 0.849** | Sent to the review queue — a human decides |
| **< 0.60** | Low-confidence inspection queue |

A "review draft" is generated even while items are pending, so you can check the output at any stage. The final submission-ready filename is only released once every queued record has a decision and QA passes.

**Available review decisions:** `APPROVE`, `REJECT_AS_NON_PII`, `RETYPE`, `ADJUST_SPAN`, `LINK_IDENTITY`, `UNLINK_IDENTITY`, `FORCE_MEDIA_REPLACEMENT`, `CLEAR_MEDIA`

---

## Replacement modes

| Mode | What it produces |
|---|---|
| `synthetic` (default) | Realistic fake names, addresses, numbers — linked across the document so the same person gets the same fake identity everywhere |
| `mask` | Stable typed tokens like `[PERSON_1]`, `[EMAIL_2]` |
| `partial` | Keeps a limited suffix (e.g. last 4 digits of a phone) where safe; falls back to masking for sensitive types |

---

## PII types detected

The tool covers 18 entity types split across identity, financial, contact, and digital categories:

| Category | Types |
|---|---|
| Identity | `PERSON`, `DOB`, `PASSPORT`, `BIOMETRIC` |
| Indian financial | `PAN`, `AADHAAR`, `GSTIN`, `CIN`, `IFSC` |
| Universal financial | `CREDIT_CARD`, `SSN` |
| Contact | `EMAIL`, `PHONE`, `ADDRESS`, `PIN_CODE` |
| Digital | `IPV4`, `QR_CODE` |
| Corporate | `COMPANY` |

---

## Known limitations

- **NER ambiguity** — spaCy can confuse public institution names, company headings, and people's names in dense legal text. The review queue exists precisely for this.
- **Address span overlap** — addresses sometimes partially overlap with phone/email contact blocks. The heuristic boundary detection handles most cases but isn't perfect.
- **OCR accuracy** — stylized logos, low-resolution scans, or degraded identity documents may not OCR cleanly. All embedded media is replaced by default to eliminate this risk entirely.
- **Full-corpus F1** — precision and recall across the full prospectus aren't reported because no independent gold corpus exists for it yet. You can supply one via the app to unlock those metrics.

---

## Data privacy

- Document content **never leaves your machine** — no API calls, no cloud processing
- `data/private/` contains raw detections and identity mappings and is excluded from git and from the shareable download bundle
- The download bundle contains only the redacted DOCX, sanitized logs (fingerprints instead of original values), and the evaluation report
- The seed is never stored in the project — it lives only in your environment variable for the duration of the session
