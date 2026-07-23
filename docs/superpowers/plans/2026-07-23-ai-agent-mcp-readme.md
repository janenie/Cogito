# AI Agent MCP README Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a root-level Chinese AI Play README that tells operators and AI agents how to configure, start, use, stop, and troubleshoot Cogito's local AI First Play MCP service.

**Architecture:** Add one operator-first `README_AI_PLAY.md` at the repository root without replacing the existing case-sensitive `Readme.md`. Keep detailed protocol and contributor material in the existing `ai_play/README.md` and Wiki, and link to them instead of duplicating internal implementation details.

**Tech Stack:** Markdown, Godot 4.7, Python 3.10+, stdio MCP, Codex TOML configuration, Claude Desktop JSON configuration.

## Global Constraints

- AI play remains opt-in; the exact Godot user argument is `-- --ai-play`.
- The Python bridge binds only to the numeric loopback address `127.0.0.1`, on port `8765` by default.
- The MCP server requires no API key and must not receive external-client credentials.
- Agent guidance may use only approved runtime observations; it must not expose scene source, node paths, hidden state, puzzle answers, repository files, or facts from `game_script/`, `code_read/`, tests, specifications, or plans.
- Escape remains the physical emergency-stop key.
- Do not run a real external MCP/model acceptance session without explicit user confirmation of screenshot, token, cost, and local trace effects.
- Do not modify `addons/input_helper/`, `addons/quick_audio/`, generated content, `.uid` files, or `.import` files.

---

### Task 1: Root AI Agent MCP Runbook

**Files:**

- Create: `README_AI_PLAY.md`
- Reference: `ai_play/README.md`
- Reference: `docs/wiki/ai-play/system-guide.md`
- Reference: `docs/wiki/development/contributor-guide.md`
- Test: `tests/check_ai_play_start_script.sh`
- Test: `tests/check_ai_play_mcp_only.sh`

**Interfaces:**

- Consumes: executable `ai_play/start_ai.sh`; MCP tools `observe()`, `act(observation_id, actions)`, and `stop()`; Godot scene `addons/cogito/DemoScenes/COGITO_3_Lobby.tscn`.
- Produces: a root onboarding runbook for generic stdio MCP hosts, Codex, Claude Desktop, and the connected playing agent.

- [ ] **Step 1: Create the root README introduction and prerequisites**

Create `README_AI_PLAY.md` in Chinese. State:

- Cogito is a Godot 4.7 first-person immersive-sim template.
- AI First Play is a local, explicitly enabled stdio MCP workflow.
- The first supported black-box play target is the `find_contract` flow in `COGITO_3_Lobby.tscn`.
- Prerequisites are Godot 4.7, Python 3.10+, and a local stdio-capable MCP host.
- The MCP server itself does not call a model and does not need an API key.

Include these environment commands:

```bash
git clone <repository-url>
cd Cogito
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
```

For Windows PowerShell, include:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r ai_play\requirements.txt
```

- [ ] **Step 2: Document generic startup order and direct diagnostics**

Explain that the MCP host normally owns the stdio process and that manually launching
`ai_play/start_ai.sh` is only a transport/diagnostic option because stdin/stdout are
reserved for MCP.

Document this order:

1. Configure/restart the MCP host so it launches the Python server.
2. Start the Lobby separately:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play
```

3. Call `observe` and wait for `status: "ready"`.

Also show the macOS/Linux direct launcher:

```bash
ai_play/start_ai.sh
```

And the Windows direct launcher:

```powershell
$env:PYTHONPATH = "ai_play/src"
.\.venv\Scripts\python.exe -m ai_play.mcp_server
```

Warn that omitting the second `--` or `--ai-play` leaves AI control disabled, and that
the server does not start, restart, or close Godot.

- [ ] **Step 3: Add Codex configuration**

Link the current official Codex MCP configuration documentation:
`https://learn.chatgpt.com/docs/extend/mcp#configure-with-configtoml`.

Use an absolute repository path in this project-scoped or user-scoped TOML example:

```toml
[mcp_servers.cogito_ai_play]
command = "/ABSOLUTE/PATH/TO/Cogito/ai_play/start_ai.sh"
cwd = "/ABSOLUTE/PATH/TO/Cogito"
startup_timeout_sec = 10
tool_timeout_sec = 40
enabled_tools = ["observe", "act", "stop"]
```

Explain that the configuration belongs in `~/.codex/config.toml`, or in
`.codex/config.toml` after trusting the project, and that Codex must be restarted or a
new session opened after changing MCP configuration.

- [ ] **Step 4: Add Claude Desktop configuration**

Link the official MCP local-server documentation:
`https://modelcontextprotocol.io/docs/develop/connect-local-servers`.

Give the macOS/Linux JSON configuration:

```json
{
  "mcpServers": {
    "cogito-ai-play": {
      "command": "/ABSOLUTE/PATH/TO/Cogito/ai_play/start_ai.sh"
    }
  }
}
```

Give the Windows JSON configuration:

```json
{
  "mcpServers": {
    "cogito-ai-play": {
      "command": "C:\\ABSOLUTE\\PATH\\TO\\Cogito\\.venv\\Scripts\\python.exe",
      "args": ["-m", "ai_play.mcp_server"],
      "env": {
        "PYTHONPATH": "C:\\ABSOLUTE\\PATH\\TO\\Cogito\\ai_play\\src"
      }
    }
  }
}
```

List the config paths:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`

Tell the operator to use absolute paths, save the file, and restart Claude Desktop.

- [ ] **Step 5: Document the agent play loop**

Give this ordered contract:

1. Call `observe()`.
2. If the result is `ready`, inspect only the returned screenshot, public player state,
   interface state, bindings, and action results.
3. Copy the returned `observation.observation_id` into the next `act` call.
4. Submit one to three actions, then treat the returned observation as the only current
   state.
5. Stop issuing actions on `game_over`, `stopped`, or `disconnected`.
6. Call `stop()` when abandoning the run or when safe progress is impossible.

Include a minimal call example:

```json
{
  "observation_id": 12,
  "actions": [
    {"type": "look", "yaw": 15, "pitch": 0},
    {"type": "move", "forward": 1, "right": 0, "duration_ms": 500}
  ]
}
```

Tell the agent never to invent or reuse an older observation ID, never to make parallel
`act` calls, and never to derive hidden knowledge from repository files.

- [ ] **Step 6: Document every allowed action and batching rule**

Include these exact JSON examples and bounds:

```json
{"type": "look", "yaw": 15, "pitch": -5}
{"type": "move", "forward": 1, "right": 0, "duration_ms": 500}
{"type": "sprint", "forward": 1, "right": 0, "duration_ms": 750}
{"type": "jump"}
{"type": "crouch"}
{"type": "interact", "action": "interact"}
{"type": "enter_digits", "digits": "1234"}
{"type": "close_ui"}
{"type": "wait", "duration_ms": 500}
{"type": "stop"}
{"type": "probe_interaction", "target_x": 0.5, "target_y": 0.5}
```

State:

- `look.yaw`: `-45..45`; `look.pitch`: `-30..30`.
- `move`/`sprint` axes: `-1..1`; duration: `50..1000` ms.
- `wait.duration_ms`: `50..2000`.
- `enter_digits`: one to six ASCII decimal digits and only while an interface is open.
- `interact.action`: only a currently advertised `interact` or `interact2`.
- `close_ui`: only while an interface is open.
- `probe_interaction`: normalized coordinates `0..1`, only while the interface is closed,
  and it must be the only action in the batch.
- A batch contains one to three actions.
- `stop`, `interact`, `enter_digits`, and `close_ui` must be the final action in a batch.

- [ ] **Step 7: Add safety, privacy, and troubleshooting**

State that:

- Physical Escape immediately stops AI control and releases simulated inputs.
- Disconnects, invalid data, shutdown, and node destruction also release held inputs.
- The bridge accepts only `127.0.0.1`; do not change it to LAN/public binding.
- The server does not persist screenshots, prompts, model context, tokens, memory, or play
  traces; the MCP host may have its own persistence behavior.
- Real external-client acceptance requires explicit operator confirmation of screenshot,
  token, cost, and trace implications.

Cover at least:

- `observation_timeout`: verify the exact Lobby command and wait for the Godot bridge.
- `disconnected`/`transport_unavailable`: confirm Godot is running and port `8765` matches.
- `stale_observation`: call `observe` or use the newest returned observation ID.
- `action_in_flight`: wait for the current `act` call; do not call it concurrently.
- `controller_busy`: close the other enabled Lobby/controller.
- Invalid action errors: compare with the current interface state and documented bounds.

Finish with links to:

- `ai_play/README.md`
- `docs/wiki/ai-play/system-guide.md`
- `docs/wiki/development/contributor-guide.md`

- [ ] **Step 8: Verify the README**

Run:

```bash
bash tests/check_ai_play_start_script.sh
bash tests/check_ai_play_mcp_only.sh
rg -n 'observe|act|stop|-- --ai-play|127\.0\.0\.1|Escape|Codex|Claude Desktop' README_AI_PLAY.md
git diff --check
```

Expected:

- Both shell tests exit `0`.
- `rg` finds every required onboarding, tool, opt-in, loopback, emergency-stop, and client
  term.
- `git diff --check` emits no output and exits `0`.

Do not start Godot or a real external MCP/model client for this documentation-only task.

- [ ] **Step 9: Commit the README and implementation plan**

```bash
git add README_AI_PLAY.md docs/superpowers/plans/2026-07-23-ai-agent-mcp-readme.md
git commit -m "docs: add AI agent MCP startup guide"
```
