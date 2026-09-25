# Required PII Types Benchmark

These are measured exact-span results on a frozen controlled benchmark. They prove executable coverage of the nine required types, but they do not substitute for full-corpus metrics on an uploaded document unless that document has independent gold annotations.

## Strict exact-span and image IoU results

| Type | Support | TP | FP | FN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| PERSON | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| EMAIL | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PHONE | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| COMPANY | 1 | 1 | 1 | 0 | 0.5000 | 1.0000 | 0.6667 |
| ADDRESS | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| SSN | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| CREDIT_CARD | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| DOB | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| IPV4 | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| PAN | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| AADHAAR | 1 | 1 | 0 | 0 | 1.0000 | 1.0000 | 1.0000 |
| PASSPORT | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| GSTIN | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| CIN | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| IFSC | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| PIN_CODE | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| BIOMETRIC | 0 | 0 | 0 | 0 | N/A | N/A | N/A |
| QR_CODE | 0 | 0 | 0 | 0 | N/A | N/A | N/A |

## Aggregate results

- Strict micro precision / recall / F1: 0.9000 / 1.0000 / 0.9474
- Relaxed precision / recall / F1: 0.9000 / 1.0000 / 0.9474
- Automatic-replacement precision: 1.0000
- Review workload: 0.1000
- Image replacement coverage: N/A
- Character accuracy: {"tpchar": 197, "tnchar": 92, "fpchar": 3, "fnchar": 0, "accuracy": 0.9897260273972602}

## Confidence bands

| Band | Predictions | TP | Precision |
|---|---:|---:|---:|
| high | 9 | 9 | 1.0000 |
| medium | 1 | 0 | 0.0000 |
| low | 0 | 0 | N/A |

## Detector contribution

{"CHECKSUM_VALIDATOR": 2, "CONTEXT_RULE": 2, "GAZETTEER": 2, "PRESIDIO_PATTERN": 3, "SPACY_NER": 2}

## Human review actions

{}
