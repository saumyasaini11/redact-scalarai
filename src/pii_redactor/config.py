from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import tomllib


@dataclass(frozen=True)
class Settings:
    project_root: Path
    input_path: Path
    final_output_path: Path
    draft_output_path: Path
    private_dir: Path
    reports_dir: Path
    mode: str
    high_threshold: float
    medium_threshold: float
    default_region: str
    company_scope: str
    replace_all_media: bool
    strict_release: bool
    spacy_model: str
    tesseract_cmd: str
    seed_env: str
    secret_seed: str | None = None

    @property
    def seed(self) -> str:
        value = self.secret_seed or os.environ.get(self.seed_env)
        if not value:
            raise RuntimeError(
                f"Required environment variable {self.seed_env} is not set. "
                "Set it to a private deterministic seed before running redaction."
            )
        return value


def load_settings(path: str | Path) -> Settings:
    config_path = Path(path).resolve()
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)
    root = config_path.parent
    paths = raw["paths"]
    redaction = raw["redaction"]
    tools = raw.get("tools", {})

    def resolved(value: str) -> Path:
        item = Path(value)
        return item if item.is_absolute() else (root / item).resolve()

    return Settings(
        project_root=root,
        input_path=resolved(paths["input"]),
        final_output_path=resolved(paths["final_output"]),
        draft_output_path=resolved(paths["draft_output"]),
        private_dir=resolved(paths["private_dir"]),
        reports_dir=resolved(paths["reports_dir"]),
        mode=redaction.get("mode", "synthetic"),
        high_threshold=float(redaction.get("high_threshold", 0.85)),
        medium_threshold=float(redaction.get("medium_threshold", 0.60)),
        default_region=redaction.get("default_region", "IN"),
        company_scope=redaction.get("company_scope", "protect"),
        replace_all_media=bool(redaction.get("replace_all_media", True)),
        strict_release=bool(redaction.get("strict_release", True)),
        spacy_model=tools.get("spacy_model", "en_core_web_md"),
        tesseract_cmd=tools.get("tesseract_cmd", ""),
        seed_env=redaction.get("seed_env", "PII_REDACTION_SEED"),
    )
