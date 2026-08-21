from __future__ import annotations

from typing import Any, Sequence

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemPermission

from tools_langgraph_deepagents import IMAGE_CONTEXT_LIMIT
from tools_langgraph_deepagents.middleware import (
    ImageLimitMiddleware,
    SerialGameTools,
)


BUILTIN_TOOLS = frozenset(
    {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "delete",
        "glob",
        "grep",
        "execute",
        "task",
    }
)


def register_game_profile() -> None:
    """Remove Deep Agents tools that are unrelated to public game play."""
    register_harness_profile(
        "openai",
        HarnessProfile(
            excluded_tools=BUILTIN_TOOLS,
            general_purpose_subagent=GeneralPurposeSubagentProfile(
                enabled=False
            ),
        ),
    )


def build_game_agent(
    *,
    model: Any,
    tools: Sequence[Any],
    system_prompt: str,
    checkpointer: Any,
) -> Any:
    register_game_profile()
    names = {tool.name for tool in tools}
    return create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=[
            ImageLimitMiddleware(IMAGE_CONTEXT_LIMIT),
            SerialGameTools(names),
        ],
        subagents=[],
        skills=None,
        memory=None,
        backend=StateBackend(),
        permissions=[
            FilesystemPermission(
                operations=["read", "write"],
                paths=["/", "/**"],
                mode="deny",
            )
        ],
        checkpointer=checkpointer,
        name="cogito-yibu-player",
    )
