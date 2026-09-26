from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
import hmac
import re

from .models import PIIRecord, PIIType, PolicyAction
from .recognizers import luhn_valid, verhoeff_valid


GIVEN_NAMES = (
    "Aarav", "Aditya", "Ananya", "Arjun", "Diya", "Isha", "Kabir", "Kavya",
    "Meera", "Neel", "Nisha", "Priya", "Rahul", "Riya", "Rohan", "Sameer",
    "Sanjay", "Tara", "Vikram", "Zoya",
)
SURNAMES = (
    "Desai", "Gupta", "Iyer", "Joshi", "Kapoor", "Mehta", "Menon", "Nair",
    "Patel", "Rao", "Shah", "Sharma", "Singh", "Verma",
)
COMPANY_STEMS = (
    "Asteron", "Bluehaven", "Cedarfield", "Crestline", "Evermont", "Harborstone",
    "Lumenridge", "Meridian", "Northstar", "Oakbridge", "Silverleaf", "Westbrook",
)
COMPANY_DESCRIPTORS = (
    "Advisory", "Capital", "Engineering", "Industries", "Infrastructure", "Logistics",
    "Manufacturing", "Power", "Securities", "Systems", "Technologies", "Ventures",
)


class Pseudonymizer:
    def __init__(self, secret_seed: str, mode: str = "synthetic"):
        self.secret = secret_seed.encode("utf-8")
        self.mode = mode
        self.cache: dict[tuple[str, str], str] = {}
        self.profiles: dict[str, dict[str, str]] = {}

    @property
    def seed_fingerprint(self) -> str:
        return sha256(self.secret).hexdigest()[:16]

    def _digest(self, material: str) -> bytes:
        return hmac.new(self.secret, material.encode("utf-8"), sha256).digest()

    def _index(self, record: PIIRecord) -> int:
        identity = record.identity_id or record.normalized_text
        digest = self._digest(f"{record.pii_type.value}|{identity}")
        return int.from_bytes(digest[:4], "big") % 9999 + 1

    def _profile(self, record: PIIRecord) -> dict[str, str]:
        identity = record.identity_id or record.record_id
        if identity in self.profiles:
            return self.profiles[identity]
        digest = self._digest(identity)
        compact_given = tuple(item for item in GIVEN_NAMES if len(item) <= 5)
        compact_surnames = tuple(item for item in SURNAMES if len(item) <= 5)
        given = compact_given[int.from_bytes(digest[:2], "big") % len(compact_given)]
        surname = compact_surnames[int.from_bytes(digest[2:4], "big") % len(compact_surnames)]
        name = f"{given} {surname}"
        slug = re.sub(r"[^a-z0-9]+", ".", name.casefold()).strip(".") or "person"
        number = int.from_bytes(digest[8:12], "big") % 100000
        company_stem = COMPANY_STEMS[int.from_bytes(digest[4:6], "big") % len(COMPANY_STEMS)]
        company_descriptor = COMPANY_DESCRIPTORS[int.from_bytes(digest[6:8], "big") % len(COMPANY_DESCRIPTORS)]
        profile = {
            "name": name,
            "email": f"{slug}.{number:05d}@example.test",
            "phone": f"+91 00000 {number:05d}",
            "address": f"{number % 199 + 1} Sample Road, Test City 000001",
            "company": f"{company_stem} {company_descriptor}",
        }
        self.profiles[identity] = profile
        return profile

    def replacement_for(self, record: PIIRecord) -> str:
        key = (record.pii_type.value, record.normalized_text)
        if key in self.cache:
            return self.cache[key]
        if self.mode == "mask":
            value = f"[{record.pii_type.value}_{self._index(record):04d}]"
        elif self.mode == "partial":
            value = self._partial(record)
        else:
            value = self._synthetic(record)
        if record.original_text.casefold() in value.casefold() or value.casefold() in record.original_text.casefold():
            value = f"[{record.pii_type.value}_{self._index(record):04d}]"
        self.cache[key] = value
        return value

    def _partial(self, record: PIIRecord) -> str:
        value = record.original_text
        if record.pii_type in {PIIType.PHONE, PIIType.AADHAAR, PIIType.PAN, PIIType.CREDIT_CARD}:
            visible = "".join(ch for ch in value if ch.isalnum())[-4:]
            return "*" * max(4, len(value) - len(visible)) + visible
        if record.pii_type == PIIType.EMAIL and "@" in value:
            local, domain = value.split("@", 1)
            return (local[:1] or "x") + "***@" + domain
        if record.pii_type == PIIType.IPV4:
            parts = value.split(".")
            return ".".join(parts[:2] + ["x", "x"])
        return f"[{record.pii_type.value}_{self._index(record):04d}]"

    def _synthetic(self, record: PIIRecord) -> str:
        profile = self._profile(record)
        index = self._index(record)
        pii_type = record.pii_type
        if pii_type == PIIType.PERSON:
            return profile["name"]
        if pii_type == PIIType.EMAIL:
            return profile["email"]
        if pii_type == PIIType.PHONE:
            return profile["phone"]
        if pii_type == PIIType.ADDRESS:
            return profile["address"]
        if pii_type == PIIType.COMPANY:
            suffix = " Private Limited"
            match = re.search(r"(?i)\b(private\s+limited|pvt\.?\s+ltd\.?|limited|ltd\.?|llp|inc\.?|corp\.?)\b", record.original_text)
            if match:
                suffix = " " + match.group(1)
            return f"{profile['company']} {index:04d}{suffix}"
        if pii_type == PIIType.DOB:
            return self._synthetic_date(record, index)
        if pii_type == PIIType.IPV4:
            host = index % 253 + 1
            return f"198.51.100.{host}"
        if pii_type == PIIType.SSN:
            return f"000-00-{index % 10000:04d}"
        if pii_type == PIIType.CREDIT_CARD:
            length = min(19, max(13, sum(ch.isdigit() for ch in record.original_text)))
            # 411111... is a reserved test-style Visa prefix. Calculate the final
            # Luhn digit so the synthetic replacement remains structurally valid.
            body = ("411111" + f"{index:012d}")[: length - 1]
            digits = body + self._luhn_check_digit(body)
            return self._restore_separators(record.original_text, digits)
        if pii_type == PIIType.PAN:
            return f"TESTX{index % 10000:04d}Z"
        if pii_type == PIIType.AADHAAR:
            digits = f"00000000{index % 10000:04d}"
            if verhoeff_valid(digits):
                digits = digits[:-1] + str((int(digits[-1]) + 1) % 10)
            return f"{digits[:4]} {digits[4:8]} {digits[8:]}"
        if pii_type == PIIType.PASSPORT:
            return f"Z{index % 10000000:07d}"
        if pii_type == PIIType.GSTIN:
            return f"00TESTX{index % 10000:04d}Z0Z0"
        if pii_type == PIIType.CIN:
            return f"U00000ZZ1900ZZZ{index % 1000000:06d}"
        if pii_type == PIIType.IFSC:
            return f"TEST9{index % 1000000:06d}"
        return f"[{pii_type.value}_{index:04d}]"

    @staticmethod
    def _luhn_check_digit(body: str) -> str:
        for digit in "0123456789":
            candidate = body + digit
            if luhn_valid(candidate):
                return digit
        raise RuntimeError("Unable to generate a Luhn-valid test card number")

    @staticmethod
    def _restore_separators(template: str, digits: str) -> str:
        iterator = iter(digits)
        result: list[str] = []
        for ch in template:
            result.append(next(iterator, "0") if ch.isdigit() else ch)
        result.extend(iterator)
        return "".join(result)

    @staticmethod
    def _synthetic_date(record: PIIRecord, index: int) -> str:
        date = datetime(1900, 1, 1) + timedelta(days=index % 365)
        original = record.original_text
        if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", original):
            return date.strftime("%d/%m/%Y")
        if re.fullmatch(r"\d{1,2}-\d{1,2}-\d{2,4}", original):
            return date.strftime("%d-%m-%Y")
        return date.strftime("%d %B %Y")


def assign_replacements(records: list[PIIRecord], pseudonymizer: Pseudonymizer) -> None:
    for record in records:
        if record.policy_action == PolicyAction.REDACT:
            record.replacement_value = pseudonymizer.replacement_for(record)
        else:
            record.replacement_value = None
