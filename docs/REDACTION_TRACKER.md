# PII Redaction Tracker

- Source SHA-256: `8b5c93f7642d659e64b51be9f6172c86c2825417f376ca1800ed331515e6f929`
- Output SHA-256: `13b2d52fcaf6fb054c248154c4f2041450adcbcccdf82035ec333ee486da7110`
- Release ready: `True`
- Total candidates reviewed: `2233`
- Automatically replaced: `207`
- Redacted by policy: `341`
- Protected by policy: `1892`
- Ignored by policy: `0`
- Approved during review: `0`
- Finalized by explicit privacy-first policy: `134`
- Rejected as non-PII: `0`
- Manual review required: `0`
- Confidence flags resolved by policy: `1641`
- Low-confidence inspection: `0`
- Embedded images replaced: `1/8`
- Text blocks preserved: `4254/4254`
- DOCX structure signature preserved: `True`

## Assignment-required PII types

Counts are detected candidates in this document. Zero means none were detected, not proof of absence.

| Type | Count |
|---|---:|
| Full names | 237 |
| Email addresses | 50 |
| Phone numbers | 33 |
| Company names | 1883 |
| Physical/mailing addresses | 19 |
| Social Security Numbers (SSNs) | 0 |
| Credit card numbers | 0 |
| Dates of birth | 0 |
| IP addresses | 0 |

## Additional detected types

| Type | Count |
|---|---:|
| CIN | 9 |
| QR_CODE | 2 |

## Policy decisions

| Action | Count |
|---|---:|
| PROTECT | 1892 |
| REDACT | 341 |

## Evidence by source

| Source | Contributions |
|---|---:|
| CHECKSUM_VALIDATOR | 33 |
| CONTEXT_RULE | 19 |
| GAZETTEER | 238 |
| POLICY | 134 |
| PRESIDIO_PATTERN | 59 |
| QR_DETECTOR | 2 |
| SPACY_NER | 2008 |

Raw originals and mappings are intentionally excluded from this tracker.
