import os
from pathlib import Path
import subprocess
import sys


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

    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr == "AI_PLAY_API_KEY is required\n"
