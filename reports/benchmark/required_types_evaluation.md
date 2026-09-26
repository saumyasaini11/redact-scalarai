# Required PII Types Benchmark

These are measured exact-span results on a frozen controlled benchmark. They prove executable coverage of the nine required types, but they do not substitute for full-corpus metrics on an uploaded document unless that document has complete gold annotations.

## Strict exact-span and image IoU results

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
| PAN | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| AADHAAR | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| PASSPORT | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| GSTIN | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| CIN | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| IFSC | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| PIN_CODE | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| BIOMETRIC | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| QR_CODE | 0 | 0 | 0 | 0 | N/A | N/A | N/A |

## Aggregate results

- Strict micro precision / recall / F1: 1.0000 / 1.0000 / 1.0000
- Relaxed precision / recall / F1: 1.0000 / 1.0000 / 1.0000
- Automatic-replacement precision: 1.0000
- Review workload: 0.1111
- Image replacement coverage: N/A
- Character accuracy: {"tpchar": 185, "tnchar": 621, "fpchar": 0, "fnchar": 0, "accuracy": 1.0}

## Block-level classification (true-negative metric)

Unit: **text block (binary: contains any labeled PII)**.

| TP | TN | FP | FN | Accuracy | Precision | Recall | F1 |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 9 | 12 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |

## Confidence bands

| Band | Predictions | TP | Precision |
|---|---:|---:|---:|
| high | 8 | 8 | 1.0000 |
| medium | 1 | 1 | 1.0000 |
| low | 0 | 0 | N/A |

## Hard negative controls

- Blocks: 12
- True-negative blocks: 12
- False-positive blocks: 0
- False-positive entities: 0

## Detector contribution

{"CHECKSUM_VALIDATOR": 2, "CONTEXT_RULE": 2, "GAZETTEER": 1, "PRESIDIO_PATTERN": 3, "SPACY_NER": 2}

## Human review actions

{}
