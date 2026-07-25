import os

from ai_host.openai_key import ensure_openai_api_key


def test_ensure_openai_api_key_reads_local_api_key_py(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    (tmp_path / "api_key.py").write_text('OPENAI_API_KEY = "sk-test"\n')

    assert ensure_openai_api_key(tmp_path)
    assert os.environ["OPENAI_API_KEY"] == "sk-test"


def test_ensure_openai_api_key_preserves_existing_env(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    (tmp_path / "api_key.py").write_text('OPENAI_API_KEY = "sk-file"\n')

    assert ensure_openai_api_key(tmp_path)
    assert os.environ["OPENAI_API_KEY"] == "sk-env"
