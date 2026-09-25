# PII Redaction Evaluation Report

## Controlled nine type benchmark

The frozen independently labeled benchmark covers PERSON, EMAIL, PHONE, ADDRESS, COMPANY, DOB, PAN, AADHAAR, and CREDIT_CARD. The production detector found all 9/9 required types.

- Strict micro precision: **0.9000**
- Strict micro recall: **1.0000**
- Strict micro F1: **0.9474**
- Character accuracy: **0.9897**

These figures are actual measured results on the controlled benchmark. They do not claim full-corpus accuracy for the prospectus. Detailed per-type results are in `reports/benchmark/required_types_evaluation.md` and `reports/benchmark/required_types_evaluation.csv`.

## Release validation

Review gate: **PASS**

- Total candidates: 2316
- Unresolved review items: 0

## Review outcomes

| Status | Count |
|---|---:|
| APPROVED | 281 |
| AUTO_APPROVED | 289 |
| REJECTED_AS_NON_PII | 1746 |

## Candidates by type

| Type | Count |
|---|---:|
| AADHAAR | 2 |
| ADDRESS | 19 |
| BIOMETRIC | 2 |
| CIN | 9 |
| COMPANY | 1959 |
| DOB | 2 |
| EMAIL | 50 |
| PAN | 1 |
| PERSON | 236 |
| PHONE | 34 |
| QR_CODE | 2 |

## Prospectus accuracy scope

Independent full-corpus gold annotations are not available; accuracy metrics are not claimed.
The CSV reports release coverage and adjudication counts. Precision, recall, and F1 remain unavailable rather than being inferred from the same detections used to create the output.
