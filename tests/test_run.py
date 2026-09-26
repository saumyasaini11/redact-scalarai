from __future__ import annotations

import subprocess
from unittest.mock import Mock

import run


def test_streamlit_exit_code_is_returned(monkeypatch) -> None:
    process = Mock()
    process.wait.return_value = 0
    monkeypatch.setattr(run.subprocess, "Popen", Mock(return_value=process))

    assert run._run_streamlit(["python", "-m", "streamlit"]) == 0


def test_keyboard_interrupt_stops_without_traceback(monkeypatch) -> None:
    process = Mock()
    process.wait.side_effect = [KeyboardInterrupt, subprocess.TimeoutExpired("wait", 5), 0]
    monkeypatch.setattr(run.subprocess, "Popen", Mock(return_value=process))

    assert run._run_streamlit(["python", "-m", "streamlit"]) == 0
    process.terminate.assert_called_once_with()
    process.kill.assert_not_called()
