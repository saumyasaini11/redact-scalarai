# PII Redaction Evaluation Report

The nine-type controlled benchmark found 9 true positives with no false positives or false negatives. The final prospectus DOCX passed release QA. This report explains the evaluation method and separates benchmark metrics from full-document checks.

## Evaluation scope

The benchmark is a **frozen manually defined gold benchmark**, not independently annotated full-document ground truth. It contains one positive exact-span fixture for each assignment-required type and twelve explicit hard-negative blocks.

Required types: `PERSON`, `EMAIL`, `PHONE`, `COMPANY`, `ADDRESS`, `SSN`, `CREDIT_CARD`, `DOB`, and `IPV4`.

## Evaluation strategy

The detector is run on a frozen set of 21 text blocks. Nine blocks each contain one manually labeled exact span for an assignment-required type. Twelve hard-negative blocks contain ordinary dates, amounts, page and order references, legal terms, identifiers, and invalid IP or card lookalikes. The gold spans and block manifest define the comparison; predictions are not used to create their own labels.

An exact entity match requires the same PII type, document part, block ID, and start and end offsets as the gold annotation. Matched predictions are true positives; unmatched predictions are false positives; unmatched gold spans are false negatives. Micro precision, recall, and F1 use these counts. Entity-level true negatives are undefined because arbitrary non-entity spans do not form a finite test set.

For classification accuracy, the unit is a text block: a block is positive when it has any gold PII span and predicted-positive when the detector emits any candidate. The fixed manifest supplies both positive and negative blocks, so TP, TN, FP, FN, accuracy, precision, recall, and F1 have explicit denominators. Character coverage is reported separately and is not called classification accuracy.

The supplied prospectus has no complete full-document gold annotations. Its release evaluation instead compares source and output hashes, verifies the DOCX can be opened, checks structural and text-block preservation, confirms selected replacements and media changes, scans processed blocks for approved originals, and requires zero unresolved policy decisions or QA errors. These checks support release readiness; they cannot establish full-document precision, recall, or absence of missed PII.

## Exact entity and span results

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

### Exact span aggregate

- TP: **9**
- FP: **0**
- FN: **0**
- Precision: **1.0000**
- Recall: **1.0000**
- F1: **1.0000**

Entity-level TN is not reported because arbitrary non-entity spans are not a finite classification unit.

## Block classification

Unit: **text block (binary: contains any labeled PII)**.

| TP | TN | FP | FN | Accuracy | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 12 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

Formulas:

- Accuracy = `(TP + TN) / (TP + TN + FP + FN)`
- Precision = `TP / (TP + FP)`
- Recall = `TP / (TP + FN)`
- F1 = `2 × Precision × Recall / (Precision + Recall)`

## Character coverage

Character TP/TN/FP/FN: **185 / 621 / 0 / 0**. Character accuracy: **1.0000**.

Character accuracy is additional coverage evidence and is not called classification accuracy.

## Full prospectus release quality assurance

The prospectus does not have full-document gold annotations, so full-document accuracy, precision, recall and F1 are **not claimed**. The following are release/QA measurements:

| Check | Result |
|---|---:|
| Candidates | 2,233 |
| Redacted/pseudonymized | 340 |
| Protected corporate facts | 1,892 |
| Ignored non-PII candidates | 1 |
| Unresolved policy-review items | 0 |
| Sensitive media replaced | 1 / 8 |
| Source/output text blocks | 4254 / 4254 |
| Structure signature preserved | True |
| Replacement application failures | 0 |
| Residual approved originals | 0 |
| Automated QA findings | 0 |
| Release gate | PASS |

Source SHA-256: `8b5c93f7642d659e64b51be9f6172c86c2825417f376ca1800ed331515e6f929`.

Output SHA-256: `c16aa903f887e47e97af2e251cb8d78478476c267c22709fb763a8866b97dc40`.

Final DOCX: `data/output/Red Herring Prospectus - Pseudonymized.docx`.

Company detection and redaction are supported. The real RHP protects legitimate corporate facts to preserve the issuer's factual content; the controlled benchmark evaluates COMPANY detection, and a strict-policy DOCX test verifies replacement.

The media audit records a decoded QR as REDACT/replaced and an undecoded square logo candidate as IGNORE/preserved. Geometric resemblance alone is not treated as sufficient evidence to replace a graphic.

## Limitations

- A 100% controlled-benchmark score does not imply 100% performance on unseen documents.
- spaCy and OCR can still produce false positives or miss fragmented/low-quality text.
- Unsupported drawing/text-box encodings may not be represented as ordinary OOXML text blocks.
- A larger independently annotated RHP sample is the next meaningful evaluation step.

Machine-readable details are in `reports/benchmark/required_types_evaluation.csv`, `reports/benchmark/required_types_report.json`, `reports/rhp_release_validation.csv`, `reports/summary_report.json`, and the packaged `reports/media_audit.json`.
