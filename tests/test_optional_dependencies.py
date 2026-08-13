"""Optional-dependency isolation checks for the Sentient integration spike."""

import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_normal_opencare_imports_do_not_require_sentient() -> None:
    # Run in a fresh interpreter: other collected test modules may have already
    # imported the SDK in this process, which would poison `sys.modules`.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app, app.main, app.agent.g2_runtime, app.integrations.sentient; "
            "import sys; "
            "assert 'sentient_agent_framework' not in sys.modules",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_adapter_import_requires_optional_extra() -> None:
    try:
        importlib.import_module("sentient_agent_framework")
    except ImportError:
        with pytest.raises(ImportError):
            importlib.import_module("app.integrations.sentient.adapter")
    else:
        importlib.import_module("app.integrations.sentient.adapter")
