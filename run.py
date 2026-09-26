"""Start the Streamlit application with the project's Python environment."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parent
VENV_DIR = PROJECT_ROOT / ".venv"
TEMP_DIR = PROJECT_ROOT / ".tmp" / "setup"
REQUIREMENTS = PROJECT_ROOT / "requirements.lock"
REQUIRED_IMPORTS = ("streamlit", "spacy", "presidio_analyzer", "docx")
SUPPORTED_PYTHON = (3, 12)


def _venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def _base_python() -> Path:
    if sys.version_info[:2] == SUPPORTED_PYTHON:
        return Path(sys.executable)
    if os.name == "nt":
        result = subprocess.run(
            ["py", "-3.12", "-c", "import sys; print(sys.executable)"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=False,
            text=True,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    raise RuntimeError("Python 3.12 is required to create the project environment.")


def _has_dependencies(python: Path) -> bool:
    imports = "; ".join(f"import {name}" for name in REQUIRED_IMPORTS)
    result = subprocess.run(
        [str(python), "-c", imports],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.returncode == 0


def _has_pip(python: Path) -> bool:
    result = subprocess.run(
        [str(python), "-m", "pip", "--version"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )
    return result.returncode == 0


def _setup_env() -> dict[str, str]:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["TEMP"] = str(TEMP_DIR)
    env["TMP"] = str(TEMP_DIR)
    return env


def _install_dependencies(python: Path) -> None:
    env = _setup_env()
    subprocess.run(
        [str(python), "-m", "pip", "install", "--upgrade", "pip"],
        cwd=PROJECT_ROOT,
        check=True,
        env=env,
    )
    subprocess.run(
        [str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        cwd=PROJECT_ROOT,
        check=True,
        env=env,
    )


def _setup_environment() -> Path:
    python = _venv_python()
    if not python.exists() or not _has_pip(python):
        subprocess.run(
            [str(_base_python()), "-m", "venv", "--clear", str(VENV_DIR)],
            cwd=PROJECT_ROOT,
            check=True,
            env=_setup_env(),
        )
    _install_dependencies(python)
    return python


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the DOCX PII Redactor web app")
    parser.add_argument(
        "--setup",
        action="store_true",
        help="create .venv (if needed) and install locked dependencies before starting",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="start the server without opening a browser window",
    )
    return parser


def _run_streamlit(command: Sequence[str]) -> int:
    process = subprocess.Popen(command, cwd=PROJECT_ROOT)
    try:
        return process.wait()
    except KeyboardInterrupt:
        # Ctrl+C is delivered to both this launcher and Streamlit on Windows.
        # Give Streamlit time to finish its own clean shutdown before forcing it.
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    python = _setup_environment() if args.setup else _venv_python()

    if not python.exists() or not _has_dependencies(python):
        print(
            "The project environment is missing or incomplete.\n"
            "Run `python run.py --setup` once, then run `python run.py`.",
            file=sys.stderr,
        )
        return 1

    command = [
        str(python),
        "-m",
        "streamlit",
        "run",
        str(PROJECT_ROOT / "app.py"),
    ]
    if args.no_browser:
        command.extend(["--server.headless", "true"])
    return _run_streamlit(command)


if __name__ == "__main__":
    raise SystemExit(main())
