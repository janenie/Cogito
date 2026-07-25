from __future__ import annotations

from typing import Protocol

from ai_host.attempt_state import AttemptContext, AttemptResult


class AgentAdapter(Protocol):
    async def run_attempt(
        self,
        context: AttemptContext,
        mcp_client: object | None,
    ) -> AttemptResult:
        """Run one game attempt and return a structured result."""
