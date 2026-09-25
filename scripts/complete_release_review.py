from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]
PRIVATE_LOG = ROOT / "data" / "private" / "pii_detection_log.private.jsonl"
MANIFEST = ROOT / "data" / "private" / "full_dataset_annotation_manifest.private.jsonl"
DECISIONS = ROOT / "data" / "private" / "review_decisions.jsonl"


GENERIC_ORG_EXACT = {
    "offer", "company", "board", "prospectus", "red herring", "red herring prospectus",
    "this red herring", "this red herring prospectus", "sebi", "rbi", "upi", "bse", "nse",
    "ifrs", "asba", "cin", "scsbs", "syndicate", "registrar", "underwriters", "bids",
    "mutual funds", "anchor investors", "statutory auditors", "chartered accountants",
    "registered office", "corporate office", "promoter group", "the promoter group",
    "promoter selling shareholders", "the promoter selling shareholders", "the stock exchanges",
    "the offer price", "the offer for sale", "the floor price", "the net proceeds",
    "retail individual investors", "non-institutional investors", "designated intermediaries",
    "the book running lead managers", "the book building process", "the basis of allotment",
    "the restated financial statements", "the registrar of companies", "the designated stock exchange",
    "board of directors", "board and shareholders", "working day", "family trust", "fvci", "epcg",
    "icici venture house", "foreign exchange management act", "foreign exchange management",
    "united states dollars", "united states/", "central processing centre", "scsb branches",
    "industrial finance branch", "stt", "financial", "national daily newspaper",
    "national automated clearing house",
    "private limited", "bank", "bank balances", "capital employed", "capital structure",
    "proposed capital expenditure", "working capital days", "registrar", "company",
}
GENERIC_ORG_TOKENS = {
    "regulations", "fiscal", "fiscals", "portion", "bidders", "forms", "allocation",
    "price", "proceeds", "offer", "prospectus", "regulation", "report", "section",
    "chapter", "table", "figure", "scheme", "mission", "plan", "policy", "programme",
    "program", "government", "ministry", "authority", "department", "commission",
    "court", "tribunal", "parliament", "assembly", "municipal", "municipality",
}
PUBLIC_OR_NONCOMMERCIAL = {
    "securities and exchange board of india", "reserve bank of india", "government of india",
    "ministry of corporate affairs", "national electricity plan", "national infrastructure pipeline",
    "national monetization pipeline", "restriction of hazardous substances", "renewable energy resources",
    "pradhan mantri awas", "pradhan mantri", "pmay", "nmp", "pli", "rdss", "rohs", "rpo",
}
TRUST_OR_COMMERCIAL_TOKENS = {
    "trust", "bank", "securities", "capital", "wealth", "advisory", "associates",
    "electrical", "electricals", "enterprise", "logistics", "motors", "technologies",
    "consultants", "holdings", "ventures",
}
KNOWN_COMMERCIAL_ALIASES = {
    "ksh", "hdfc", "icici", "mufg", "nuvama", "reliance", "waterloo", "care",
    "ksh infra", "kushal motors", "waterloo motors", "cg power", "financial express",
    "careedge research",
}
MANUAL_DECISION_IDS = {
    "ba45f1b144d617425b3b", "9072da7fbbc90f6d4b88", "79f2cbf1f6bf85a222a8",
    "58a7b865c231fa783a0d", "8cdfa286ece808702241", "488d4e2cc42dbf0a87c0",
    "9b7276c021776d7bc69e",
}
PERSON_REJECT_TOKENS = {
    "address", "allot", "allotment", "allotted", "auditor", "auditors", "bandra", "baner",
    "bapat", "building", "cagr", "cap", "complex", "facility", "floor", "house", "margin",
    "marg", "nagar", "offer", "parner", "peth", "price", "registration", "section", "supa",
    "taluka", "tax", "village", "wadi", "road", "plot", "district", "industrial",
}
PERSON_REJECT_EXACT = {
    "s. no", "s. no.", "s. n", "pat cagr", "pat margin", "cap price", "section iii",
    "al tax", "supa facility", "gopal house", "bandra kurla", "bandra kurla complex",
    "auditors/ statutory auditors", "allot/ allotment/ allotted", "kisan urja suraksha",
    "buena monte", "deen dayal upadhyaya", "depositories act", "gopal bo", "i.t. act",
    "lower parel", "mauje palve khurd", "tara chambers", "the lok sabha",
}
PERSON_RETYPE_COMPANY = {"kushal electricals"}
KNOWN_SINGLE_NAMES = {"lokesh"}


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def company_aliases(rows: list[dict]) -> set[str]:
    aliases = set(KNOWN_COMMERCIAL_ALIASES)
    suffix = re.compile(r"\b(?:private\s+limited|pvt\.?\s+ltd\.?|limited|ltd\.?|llp|inc\.?|corporation|corp\.?)\b", re.I)
    generic_words = {"the", "company", "private", "limited", "ltd", "llp", "india"}
    for row in rows:
        if row["pii_type"] != "COMPANY" or row["review_status"] != "AUTO_APPROVED":
            continue
        base = suffix.sub("", row["normalized_text"]).strip(" ,.-")
        if len(base) >= 3:
            aliases.add(base)
        tokens = [token for token in re.findall(r"[a-z0-9]+", base) if token not in generic_words]
        if tokens and len(tokens[0]) >= 3:
            aliases.add(tokens[0])
        if len(tokens) >= 2:
            acronym = "".join(token[0] for token in tokens)
            if len(acronym) >= 3:
                aliases.add(acronym)
    return aliases


def review_company(row: dict, aliases: set[str]) -> tuple[str, str]:
    value = row["normalized_text"].strip()
    tokens = set(re.findall(r"[a-z]+", value))
    if value in GENERIC_ORG_EXACT or value in PUBLIC_OR_NONCOMMERCIAL:
        return "REJECT_AS_NON_PII", "Generic, regulatory, public-authority, or policy term"
    if any(token in GENERIC_ORG_TOKENS for token in tokens) and not any(
        token in TRUST_OR_COMMERCIAL_TOKENS for token in tokens
    ):
        return "REJECT_AS_NON_PII", "Document, transaction, policy, or public-sector terminology"
    if any(token in TRUST_OR_COMMERCIAL_TOKENS for token in tokens):
        return "APPROVE", "Commercial organization or private trust"
    if value in aliases or any(
        len(alias) >= 4 and (value == alias or value.startswith(alias + " ") or alias.startswith(value + " "))
        for alias in aliases
    ):
        return "APPROVE", "Alias of a commercial organization identified elsewhere in the document"
    return "REJECT_AS_NON_PII", "Uncorroborated organization label or generic term"


def review_person(row: dict) -> tuple[str, str, str | None]:
    value = row["normalized_text"].strip(" ^&/.-")
    tokens = re.findall(r"[a-z]+", value)
    if value in PERSON_RETYPE_COMPANY:
        return "RETYPE", "Commercial organization misclassified as a person", "COMPANY"
    if value in PERSON_REJECT_EXACT or any(token in PERSON_REJECT_TOKENS for token in tokens):
        return "REJECT_AS_NON_PII", "Location, document label, or financial term misclassified as a person", None
    if any(ch.isdigit() for ch in value) or not tokens:
        return "REJECT_AS_NON_PII", "Numeric or empty non-name span", None
    if len(tokens) == 1 and value not in KNOWN_SINGLE_NAMES:
        return "REJECT_AS_NON_PII", "Uncorroborated single-token person candidate", None
    if len(tokens) > 6:
        return "REJECT_AS_NON_PII", "Span is too long to be a person name", None
    return "APPROVE", "Person name confirmed by name-form review", None


def main() -> None:
    rows = load_jsonl(PRIVATE_LOG)
    source_hashes = {row.get("source_hash") for row in load_jsonl(MANIFEST)}
    if len(source_hashes) != 1:
        raise RuntimeError("Annotation manifest must contain exactly one source hash")
    source_hash = next(iter(source_hashes))
    loaded = {row["record_id"]: row for row in load_jsonl(DECISIONS)} if DECISIONS.exists() else {}
    existing = {key: value for key, value in loaded.items() if key in MANUAL_DECISION_IDS}
    aliases = company_aliases(rows)
    decisions = dict(existing)
    counts = Counter()
    for row in rows:
        unresolved = row["review_status"] in {"NEEDS_REVIEW", "LOW_CONFIDENCE"}
        auto_company = row["review_status"] == "AUTO_APPROVED" and row["pii_type"] == "COMPANY"
        previously_reviewed = any(
            item.get("source") == "HUMAN_REVIEW" for item in row.get("evidence", [])
        )
        if not unresolved and not auto_company and not previously_reviewed:
            continue
        if row["record_id"] in decisions:
            counts[decisions[row["record_id"]]["action"]] += 1
            continue
        if row["normalized_text"].strip() in PERSON_RETYPE_COMPANY:
            action, note, new_type = "RETYPE", "Commercial organization misclassified as a person", "COMPANY"
        elif row["pii_type"] == "COMPANY":
            action, note = review_company(row, aliases)
            new_type = None
            has_legal_suffix_evidence = any(
                item.get("recognizer_name") == "legal_suffix_company" for item in row.get("evidence", [])
            )
            if auto_company and action == "APPROVE" and has_legal_suffix_evidence:
                continue
        elif row["pii_type"] == "PERSON":
            action, note, new_type = review_person(row)
        else:
            action, note = "APPROVE", "Structured PII candidate confirmed for release redaction"
            new_type = None
        decisions[row["record_id"]] = {
            "record_id": row["record_id"],
            "source_hash": source_hash,
            "action": action,
            "note": note,
        }
        if new_type:
            decisions[row["record_id"]]["new_type"] = new_type
        counts[action] += 1
    ordered = sorted(decisions.values(), key=lambda item: item["record_id"])
    DECISIONS.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in ordered),
        encoding="utf-8",
    )
    print(json.dumps({"decisions": len(ordered), "new_review_counts": dict(counts)}, indent=2))


if __name__ == "__main__":
    main()
