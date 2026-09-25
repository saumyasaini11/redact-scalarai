from __future__ import annotations

from hashlib import sha256
import ipaddress
import re
import unicodedata
from typing import Iterable

import phonenumbers
from presidio_analyzer import Pattern, PatternRecognizer
import spacy

from .models import DetectionSource, Evidence, PIIRecord, PIIType, TextBlock


PUBLIC_AUTHORITY_TERMS = {
    "securities and exchange board of india",
    "government of india",
    "income tax department",
    "reserve bank of india",
    "ministry of corporate affairs",
}
COMMERCIAL_SIGNALS = (
    "limited", "ltd", "private", "pvt", "llp", "bank", "securities",
    "technologies", "industries", "enterprise", "company", "corporation",
    "consultants", "services", "capital", "registrar", "associates",
)
NAME_CONTEXT = ("contact person", "name:", "director", "promoter", "father's name", "father name")
ADDRESS_TERMS = (
    "address", "registered office", "corporate office", "road", "street", "lane",
    "nagar", "colony", "floor", "building", "plot", "district", "sector", "village",
)
NEGATIVE_NUMBER_CONTEXT = (
    "order", "ticket", "invoice", "transaction", "reference", "registration",
    "employee id", "product id", "cin", "gstin", "folio", "application no",
)
DOB_CONTEXT = ("dob", "date of birth", "born on", "birth date")
BANK_CONTEXT = ("account", "bank account", "beneficiary", "bank details")
DATASET_PERSON_GAZETTEER = (
    "Kushal Subbayya Hegde",
    "Pushpa Kushal Hegde",
    "Rajesh Kushal Hegde",
    "Rohit Kushal Hegde",
    "Rakhi Girija Shetty",
    "Pushpa Hegde",
)


def normalize_value(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def record_id(block: TextBlock, pii_type: PIIType, start: int, end: int, value: str) -> str:
    material = f"{block.block_id}|{pii_type.value}|{start}|{end}|{normalize_value(value)}"
    return sha256(material.encode("utf-8")).hexdigest()[:20]


def evidence(source: DetectionSource, name: str, score: float, reason: str,
             contexts: Iterable[str] = (), validators: Iterable[str] = ()) -> Evidence:
    return Evidence(
        source=source,
        recognizer_name=name,
        score=min(0.99, max(0.0, score)),
        reason=reason,
        matched_context=tuple(contexts),
        validator_results=tuple(validators),
    )


def make_record(block: TextBlock, pii_type: PIIType, start: int, end: int,
                item_evidence: Evidence) -> PIIRecord:
    value = block.text[start:end]
    return PIIRecord(
        record_id=record_id(block, pii_type, start, end, value),
        pii_type=pii_type,
        original_text=value,
        normalized_text=normalize_value(value),
        source_kind="native_text",
        document_part=block.part_name,
        block_id=block.block_id,
        start_offset=start,
        end_offset=end,
        evidence=[item_evidence],
        final_confidence=item_evidence.score,
    )


def luhn_valid(number: str) -> bool:
    digits = [int(ch) for ch in number if ch.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    parity = len(digits) % 2
    for index, digit in enumerate(digits):
        if index % 2 == parity:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


_VERHOEFF_D = (
    (0,1,2,3,4,5,6,7,8,9),(1,2,3,4,0,6,7,8,9,5),(2,3,4,0,1,7,8,9,5,6),
    (3,4,0,1,2,8,9,5,6,7),(4,0,1,2,3,9,5,6,7,8),(5,9,8,7,6,0,4,3,2,1),
    (6,5,9,8,7,1,0,4,3,2),(7,6,5,9,8,2,1,0,4,3),(8,7,6,5,9,3,2,1,0,4),
    (9,8,7,6,5,4,3,2,1,0),
)
_VERHOEFF_P = (
    (0,1,2,3,4,5,6,7,8,9),(1,5,7,6,2,8,3,0,9,4),(5,8,0,3,7,9,6,1,4,2),
    (8,9,1,6,0,4,3,5,2,7),(9,4,5,3,1,2,6,8,7,0),(4,2,8,6,5,7,3,9,0,1),
    (2,7,9,3,8,0,6,4,1,5),(7,0,4,6,9,1,3,2,5,8),
)


def verhoeff_valid(value: str) -> bool:
    digits = [int(ch) for ch in value if ch.isdigit()]
    if len(digits) != 12:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        checksum = _VERHOEFF_D[checksum][_VERHOEFF_P[index % 8][digit]]
    return checksum == 0


class StructuredRecognizerSet:
    def __init__(self, default_region: str = "IN"):
        self.default_region = default_region
        self.patterns: list[tuple[PIIType, PatternRecognizer]] = [
            self._pattern(PIIType.EMAIL, "email", r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+\b", 0.95),
            self._pattern(PIIType.SSN, "us_ssn", r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)", 0.85),
            self._pattern(PIIType.IPV4, "ipv4", r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])", 0.85),
            self._pattern(PIIType.PAN, "india_pan", r"(?<![A-Z0-9])[A-Z]{5}[0-9]{4}[A-Z](?![A-Z0-9])", 0.85),
            self._pattern(PIIType.AADHAAR, "aadhaar", r"(?<!\d)\d{4}[ -]?\d{4}[ -]?\d{4}(?!\d)", 0.85),
            self._pattern(PIIType.PASSPORT, "india_passport", r"(?<![A-Z0-9])[A-Z][0-9]{7}(?![A-Z0-9])", 0.60),
            self._pattern(PIIType.GSTIN, "gstin", r"(?<![A-Z0-9])[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z]Z[0-9A-Z](?![A-Z0-9])", 0.85),
            self._pattern(PIIType.CIN, "cin", r"(?<![A-Z0-9])[LU][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}(?![A-Z0-9])", 0.85),
            self._pattern(PIIType.IFSC, "ifsc", r"(?<![A-Z0-9])[A-Z]{4}0[A-Z0-9]{6}(?![A-Z0-9])", 0.60),
        ]
        self.card_pattern = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")
        self.date_pattern = re.compile(
            r"(?i)(?<!\d)(?:\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
            r"\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
            r"Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})(?!\d)"
        )
        self.company_pattern = re.compile(
            r"\b[A-Z][A-Za-z0-9&.'()/-]*(?:\s+[A-Z][A-Za-z0-9&.'()/-]*){0,8}\s+"
            r"(?:Private\s+Limited|Pvt\.?\s+Ltd\.?|Limited|Ltd\.?|LLP|Inc\.?|Corporation|Corp\.?)\b"
        )

    @staticmethod
    def _pattern(pii_type: PIIType, name: str, regex: str, score: float):
        recognizer = PatternRecognizer(
            supported_entity=pii_type.value,
            name=f"{name}_presidio_recognizer",
            patterns=[Pattern(name=name, regex=regex, score=score)],
        )
        return pii_type, recognizer

    def detect(self, blocks: list[TextBlock]) -> list[PIIRecord]:
        found: list[PIIRecord] = []
        for block in blocks:
            lower = block.text.casefold()
            for pii_type, recognizer in self.patterns:
                for result in recognizer.analyze(block.text, [pii_type.value], nlp_artifacts=None):
                    value = block.text[result.start:result.end]
                    score = float(result.score)
                    validators: list[str] = []
                    reason = f"Matched {recognizer.name}"
                    if pii_type == PIIType.IPV4:
                        try:
                            ipaddress.IPv4Address(value)
                            score = 0.95
                            validators.append("valid IPv4")
                        except ValueError:
                            continue
                    elif pii_type == PIIType.SSN:
                        a, g, s = value.split("-")
                        if a == "000" or a == "666" or 900 <= int(a) <= 999 or g == "00" or s == "0000":
                            continue
                        score = 0.95
                        validators.append("valid SSN structure")
                    elif pii_type == PIIType.AADHAAR:
                        if not verhoeff_valid(value):
                            score = 0.70 if "aadhaar" in lower else 0.55
                            validators.append("Verhoeff failed or OCR uncertain")
                        else:
                            score = 0.98
                            validators.append("Verhoeff valid")
                    elif pii_type == PIIType.PASSPORT:
                        nearby = lower[max(0, result.start - 40): min(len(lower), result.end + 40)]
                        if "passport" not in nearby:
                            continue
                        score = 0.93
                    elif pii_type == PIIType.IFSC:
                        nearby = lower[max(0, result.start - 60): min(len(lower), result.end + 60)]
                        score = 0.93 if "ifsc" in nearby and any(term in nearby for term in BANK_CONTEXT) else 0.60
                    item = make_record(
                        block, pii_type, result.start, result.end,
                        evidence(DetectionSource.PRESIDIO_PATTERN, recognizer.name, score, reason, validators=validators),
                    )
                    found.append(item)

            for match in phonenumbers.PhoneNumberMatcher(block.text, self.default_region):
                nearby = lower[max(0, match.start - 35): min(len(lower), match.end + 35)]
                if any(term in nearby for term in NEGATIVE_NUMBER_CONTEXT):
                    continue
                score = 0.95 if phonenumbers.is_valid_number(match.number) else 0.85
                found.append(make_record(
                    block, PIIType.PHONE, match.start, match.end,
                    evidence(DetectionSource.CHECKSUM_VALIDATOR, "phonenumbers", score,
                             "Parsed as a possible or valid phone number",
                             validators=("valid" if score == 0.95 else "possible",)),
                ))

            for match in self.card_pattern.finditer(block.text):
                nearby = lower[max(0, match.start() - 40): min(len(lower), match.end() + 40)]
                if any(term in nearby for term in NEGATIVE_NUMBER_CONTEXT):
                    continue
                if luhn_valid(match.group()):
                    found.append(make_record(
                        block, PIIType.CREDIT_CARD, match.start(), match.end(),
                        evidence(DetectionSource.CHECKSUM_VALIDATOR, "luhn_card", 0.98,
                                 "13-19 digit candidate passed Luhn", validators=("Luhn valid",)),
                    ))

            for match in self.date_pattern.finditer(block.text):
                nearby = lower[max(0, match.start() - 55): min(len(lower), match.end() + 30)]
                contexts = tuple(term for term in DOB_CONTEXT if term in nearby)
                if contexts:
                    found.append(make_record(
                        block, PIIType.DOB, match.start(), match.end(),
                        evidence(DetectionSource.CONTEXT_RULE, "dob_context", 0.93,
                                 "Date appears in birth context", contexts=contexts),
                    ))

            for match in self.company_pattern.finditer(block.text):
                value_lower = normalize_value(match.group())
                if value_lower in PUBLIC_AUTHORITY_TERMS:
                    continue
                found.append(make_record(
                    block, PIIType.COMPANY, match.start(), match.end(),
                    evidence(DetectionSource.GAZETTEER, "legal_suffix_company", 0.93,
                             "Commercial legal suffix matched", validators=("legal suffix",)),
                ))

            for person_name in DATASET_PERSON_GAZETTEER:
                for match in re.finditer(re.escape(person_name), block.text, re.IGNORECASE):
                    found.append(make_record(
                        block, PIIType.PERSON, match.start(), match.end(),
                        evidence(DetectionSource.GAZETTEER, "dataset_person_gazetteer", 0.93,
                                 "Confirmed person name from the supplied-dataset review"),
                    ))

            address_contexts = tuple(term for term in ADDRESS_TERMS if term in lower)
            pin_match = re.search(r"(?<!\d)[1-9]\d{5}(?!\d)", block.text)
            if address_contexts and (pin_match or len(address_contexts) >= 2) and len(block.text) <= 350:
                start = 0
                colon = block.text.find(":")
                if colon >= 0 and colon < 80:
                    start = colon + 1
                    while start < len(block.text) and block.text[start].isspace():
                        start += 1
                tail = block.text[start:]
                boundary = re.search(
                    r"(?i)(?:\s{2,}|[;|])(?:telephone|phone|mobile|e-mail|email|website|fax|"
                    r"contact(?:\s+person)?|cin|gstin)\s*:",
                    tail,
                )
                end = start + boundary.start() if boundary else len(block.text)
                while end > start and block.text[end - 1].isspace():
                    end -= 1
                if len(block.text[start:end].strip()) >= 12:
                    found.append(make_record(
                        block, PIIType.ADDRESS, start, end,
                        evidence(DetectionSource.CONTEXT_RULE, "address_context", 0.85,
                                 "Address terms and postal/structural evidence matched", contexts=address_contexts),
                    ))
        return found


class SpacyEntityRecognizer:
    def __init__(self, model_name: str):
        self.nlp = spacy.load(model_name, disable=["tagger", "parser", "lemmatizer"])
        self.nlp.max_length = 2_000_000

    def detect(self, blocks: list[TextBlock]) -> list[PIIRecord]:
        found: list[PIIRecord] = []
        stream = ((block.text, block) for block in blocks)
        for document, block in self.nlp.pipe(stream, as_tuples=True, batch_size=32):
            lower = block.text.casefold()
            for entity in document.ents:
                if entity.label_ == "PERSON":
                    tokens = [token for token in entity.text.split() if token]
                    nearby = lower[max(0, entity.start_char - 50): min(len(lower), entity.end_char + 25)]
                    contexts = tuple(term for term in NAME_CONTEXT if term in nearby)
                    if len(tokens) < 2 and not contexts:
                        continue
                    score = 0.82 if contexts else 0.75
                    found.append(make_record(
                        block, PIIType.PERSON, entity.start_char, entity.end_char,
                        evidence(DetectionSource.SPACY_NER, "spacy_person", score,
                                 "spaCy PERSON entity", contexts=contexts),
                    ))
                elif entity.label_ == "ORG":
                    value_lower = normalize_value(entity.text)
                    if value_lower in PUBLIC_AUTHORITY_TERMS:
                        continue
                    signals = tuple(term for term in COMMERCIAL_SIGNALS if term in value_lower)
                    score = 0.85 if signals else 0.60
                    found.append(make_record(
                        block, PIIType.COMPANY, entity.start_char, entity.end_char,
                        evidence(DetectionSource.SPACY_NER, "spacy_org", score,
                                 "spaCy ORG entity", contexts=signals),
                    ))
        return found


def detect_all(blocks: list[TextBlock], default_region: str, spacy_model: str) -> list[PIIRecord]:
    structured = StructuredRecognizerSet(default_region).detect(blocks)
    nlp_records = SpacyEntityRecognizer(spacy_model).detect(blocks)
    return structured + nlp_records
