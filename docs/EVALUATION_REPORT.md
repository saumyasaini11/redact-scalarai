# Final Evaluation Report

This report is generated from `reports/benchmark/required_types_report.json` and `reports/summary_report.json`. It separates controlled benchmark metrics from full-document release QA.

## 1. Evaluation scope

The benchmark is a **frozen manually defined gold benchmark**, not independently annotated full-document ground truth. It contains one positive exact-span fixture for each assignment-required type and twelve explicit hard-negative blocks.

Required types: `PERSON`, `EMAIL`, `PHONE`, `COMPANY`, `ADDRESS`, `SSN`, `CREDIT_CARD`, `DOB`, and `IPV4`.

## 2. Exact entity/span results

| Type | Support | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| PERSON | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| EMAIL | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PHONE | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| COMPANY | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| ADDRESS | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| SSN | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| CREDIT_CARD | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DOB | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| IPV4 | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |

### Exact-span aggregate

- TP: **9**
- FP: **0**
- FN: **0**
- Precision: **1.0000**
- Recall: **1.0000**
- F1: **1.0000**

Entity-level TN is not reported because arbitrary non-entity spans are not a finite classification unit.

## 3. Block-level classification

Unit: **text block (binary: contains any labeled PII)**.

| TP | TN | FP | FN | Accuracy | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 12 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

Formulas:

- Accuracy = `(TP + TN) / (TP + TN + FP + FN)`
- Precision = `TP / (TP + FP)`
- Recall = `TP / (TP + FN)`
- F1 = `2 × Precision × Recall / (Precision + Recall)`

## 4. Additional character metric

Character TP/TN/FP/FN: **185 / 621 / 0 / 0**. Character accuracy: **1.0000**.

Character accuracy is additional coverage evidence and is not called classification accuracy.

## 5. Full RHP release QA

The prospectus does not have full-document gold annotations, so full-document accuracy, precision, recall and F1 are **not claimed**. The following are release/QA measurements:

| Check | Result |
|---|---:|
| Candidates | 2,233 |
| Redacted/pseudonymized | 341 |
| Protected corporate facts | 1,892 |
| Unresolved policy-review items | 0 |
| Sensitive media replaced | 1 / 8 |
| Source/output text blocks | 4254 / 4254 |
| Structure signature preserved | True |
| Replacement application failures | 0 |
| Residual approved originals | 0 |
| Automated QA findings | 0 |
| Release gate | PASS |

Output SHA-256: `13b2d52fcaf6fb054c248154c4f2041450adcbcccdf82035ec333ee486da7110`.

Final DOCX: `data/output/Red Herring Prospectus - Pseudonymized.docx`.

Corporate facts are detected separately from policy. The real RHP uses company protection, while the controlled benchmark still evaluates COMPANY detection.

## 6. Limitations

- A 100% controlled-benchmark score does not imply 100% performance on unseen documents.
- spaCy and OCR can still produce false positives or miss fragmented/low-quality text.
- Unsupported drawing/text-box encodings may not be represented as ordinary OOXML text blocks.
- A larger independently annotated RHP sample is the next meaningful evaluation step.

Machine-readable details are in `reports/benchmark/required_types_evaluation.csv`, `reports/benchmark/required_types_report.json`, `reports/rhp_release_validation.csv`, and `reports/summary_report.json`.
