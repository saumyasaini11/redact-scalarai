# Redaction Implementations Comparison

## Outcome

The Streamlit release keeps the reference output's strong layout preservation while retaining the existing codebase's safer package-wide redaction, deterministic pseudonyms, explainable confidence, review gating, embedded-media replacement, and residual-value QA.

## Measured comparison on the supplied prospectus

| Area | Supplied redacted document | Streamlit release baseline |
|---|---:|---:|
| Extracted DOCX text blocks preserved | 4,254 | 4,254 |
| Embedded media assets present | 8 | 8 |
| Embedded media unchanged from source | 8 of 8 | 0 of 8 |
| Residual occurrences of a reviewed person identity | 3 | 0 |
| Deterministic cross-document identity mapping | Not demonstrable from the output alone | Built in |
| Confidence and human-review evidence | Not embedded as a reproducible workflow | Built in |
| Package-wide residual and reopen QA | Not demonstrable from the output alone | Built in |

The supplied redacted document preserves the original package size and media bytes, so text contained in images remains a disclosure risk. The retained implementation replaces sensitive media while preserving each media relationship and dimensions in the DOCX layout.

## Evaluation closure

The controlled benchmark is independently labeled and exercises PERSON, EMAIL, PHONE, ADDRESS, COMPANY, DOB, PAN, AADHAAR, and CREDIT_CARD. The measured strict micro results are precision 0.9000, recall 1.0000, and F1 0.9474, with all 9 required types detected. Prospectus-specific precision and recall remain correctly unclaimed until independent gold annotations are supplied through the app.
