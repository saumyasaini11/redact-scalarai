# RHP Release QA Report

## Release validation

Review gate: **PASS**

- Total candidates: 2233
- Unresolved review items: 0
- Source SHA-256: `8b5c93f7642d659e64b51be9f6172c86c2825417f376ca1800ed331515e6f929`
- Output SHA-256: `c16aa903f887e47e97af2e251cb8d78478476c267c22709fb763a8866b97dc40`
- Sensitive media replaced: 1 / 8

## Detection confidence status

A `NEEDS_REVIEW` confidence flag is not unresolved when the explicit company/protection policy has already classified it.

| Status | Count |
|---|---:|
| APPROVED | 134 |
| AUTO_APPROVED | 457 |
| NEEDS_REVIEW | 1641 |
| REJECTED_AS_NON_PII | 1 |

## Final policy actions

| Action | Count |
|---|---:|
| IGNORE | 1 |
| PROTECT | 1892 |
| REDACT | 340 |

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

## Accuracy scope

Complete full-corpus gold annotations are not available; accuracy metrics are not claimed.
The CSV reports release coverage and adjudication counts. Precision, recall, and F1 remain unavailable rather than being inferred from the same detections used to create the output.
