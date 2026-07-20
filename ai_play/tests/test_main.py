import os
from pathlib import Path
import subprocess
import sys

import pytest

from ai_play import main as main_module


def test_module_entry_reports_missing_key_without_traceback():
    env = os.environ.copy()
    env.pop("AI_PLAY_API_KEY", None)
    source_dir = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(source_dir)

    result = subprocess.run(
        [sys.executable, "-m", "ai_play.main"],
        capture_output=True,
        check=False,
        env=env,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "AI_PLAY_API_KEY is required\n"


def test_cli_does_not_hide_value_error_after_configuration(monkeypatch):
    test_key = "test-key"
    config = main_module.Config(api_key=test_key)
    monkeypatch.setattr(main_module.Config, "from_env", lambda: config)
    monkeypatch.setattr(
        main_module,
        "serve",
        lambda *_args: (_ for _ in ()).throw(ValueError("serve failed")),
    )

    with pytest.raises(ValueError, match="serve failed"):
        main_module._run_cli([])
