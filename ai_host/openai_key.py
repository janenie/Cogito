from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def ensure_openai_api_key(repo_root: Path | None = None) -> bool:
    """Load OPENAI_API_KEY from local api_key.py when the environment is unset."""
    if os.environ.get("OPENAI_API_KEY"):
        return True
    root = repo_root or Path.cwd()
    key_file = root / "api_key.py"
    if not key_file.is_file():
        return False
    spec = importlib.util.spec_from_file_location("_ai_host_local_api_key", key_file)
    if spec is None or spec.loader is None:
        return False
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    value = (
        getattr(module, "OPENAI_API_KEY", None)
        or getattr(module, "API_KEY", None)
        or getattr(module, "api_key", None)
    )
    if isinstance(value, str) and value.strip():
        os.environ["OPENAI_API_KEY"] = value.strip()
        return True
    return False
