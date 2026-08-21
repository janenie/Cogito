from pathlib import Path

import pytest

from tools_langgraph_deepagents.config import parse_args
from tools_langgraph_deepagents.credentials import load_yibu_credentials


def test_defaults_use_chat_gemini_and_newak():
    args = parse_args([])

    assert args.model == "gemini-3.6-flash"
    assert args.yibu_credentials.name == "newak.py"
    assert args.credential_name == "ak"
    assert args.runs == 3


def test_explicit_external_confirmation_is_a_flag():
    args = parse_args(["--confirm-external-run"])

    assert args.confirm_external_run is True


def test_loads_only_selected_literal_dictionary(tmp_path: Path):
    source = tmp_path / "keys.py"
    source.write_text(
        "ak1 = {'key': 'first', 'url': 'https://yibuapi.com'}\n"
        "ak = {'key': 'chosen', 'url': 'https://yibuapi.com/v1'}\n",
        encoding="utf-8",
    )

    credentials = load_yibu_credentials(source, "ak")

    assert credentials.api_key == "chosen"
    assert credentials.base_url == "https://yibuapi.com/v1"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("ak = dynamic()", "literal dictionary"),
        ("ak = {'key': '', 'url': 'https://yibuapi.com'}", "non-empty"),
        ("ak = {'key': 'x', 'url': 'http://yibuapi.com'}", "https"),
        (
            "ak = {'key': 'x', 'url': 'https://user@yibuapi.com'}",
            "credentials",
        ),
    ],
)
def test_rejects_unsafe_credentials(
    tmp_path: Path,
    text: str,
    message: str,
):
    source = tmp_path / "keys.py"
    source.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match=message):
        load_yibu_credentials(source, "ak")
