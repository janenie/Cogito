import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from ai_play import main as main_module


def test_module_entry_reports_missing_key_without_traceback(tmp_path):
    env = os.environ.copy()
    env.pop("AI_PLAY_API_KEY", None)
    source_dir = Path(__file__).resolve().parents[1] / "src"
    env["PYTHONPATH"] = str(source_dir)

    result = subprocess.run(
        [sys.executable, "-m", "ai_play.main"],
        capture_output=True,
        check=False,
        cwd=tmp_path,
        env=env,
        text=True,
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "AI_PLAY_API_KEY is required\n"


def test_cli_does_not_hide_value_error_after_configuration(monkeypatch, tmp_path):
    test_key = "test-key"
    config = main_module.Config(api_key=test_key, log_root=tmp_path)
    monkeypatch.setattr(main_module.Config, "from_env", lambda: config)
    monkeypatch.setattr(
        main_module,
        "serve",
        lambda *_args: (_ for _ in ()).throw(ValueError("serve failed")),
    )

    with pytest.raises(ValueError, match="serve failed"):
        main_module._run_cli([])


def test_main_creates_one_run_logger_for_the_sidecar(monkeypatch, tmp_path):
    created = {}
    logger = SimpleNamespace(run_dir=tmp_path / "test-model" / "run")
    logger.close = lambda: created.update(logger_closed=True)

    class FakeRunLogger:
        @classmethod
        def create(cls, root, model):
            created["logger_args"] = (root, model)
            return logger

    def fake_agent_loop(api_client, memory, **kwargs):
        created["agent_logger"] = kwargs["run_logger"]
        return SimpleNamespace()

    monkeypatch.setattr(main_module, "RunLogger", FakeRunLogger)
    monkeypatch.setattr(main_module, "ApiClient", lambda config: SimpleNamespace())
    monkeypatch.setattr(main_module, "AgentLoop", fake_agent_loop)
    monkeypatch.setattr(main_module, "serve", lambda config, agent: None)
    config = main_module.Config(
        api_key="test-key",
        model="test-model",
        log_root=tmp_path,
    )

    main_module.main([], config=config)

    assert created["logger_args"] == (tmp_path, "test-model")
    assert created["agent_logger"] is logger
    assert created["logger_closed"] is True
