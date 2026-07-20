# AI First Play operator guide

AI First Play connects the COGITO Lobby to a local Python sidecar. The Godot
controller is installed in the Lobby but is deliberately disabled at startup;
the operator remains in control of when screenshots begin leaving the game.

## Setup and start

From the repository root, create the environment and enter a newly rotated API
key without echoing it or putting it in shell history:

```bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
read -rs AI_PLAY_API_KEY
export AI_PLAY_API_KEY
PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.main
```

Start the Lobby with the exact Godot user argument below only after the sidecar
is listening:

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play
```

The argument after `--` is an explicit per-run opt-in. The Lobby instance keeps
`auto_start = false`, so launching it normally does not enable AI. Call
`disable_ai()` on `AIPlayController` to stop normally.

The sidecar listens only on `127.0.0.1:8765`. `AI_PLAY_WS_PORT` can change the
port, and the controller must be configured to match it. `AI_PLAY_BASE_URL` and
`AI_PLAY_MODEL` select a custom OpenAI-compatible provider. That endpoint and
model must support multimodal Chat Completions content, including a text part
and a base64 `image_url` part; text-only compatibility is insufficient.

## Controls and safety

AI movement is sent through ordinary COGITO input and physics. `interact` and
`interact2` are contextual action slots, not permanent meanings: the current
visible interaction list supplies their prompt and current binding (normally F
and E). The agent may select one only while it appears in that list.

Press F12 for an emergency stop. Any physical keyboard, mouse, or controller
input also triggers immediate human takeover. Both paths disconnect AI and
release held movement (`forward`, `back`, `left`, `right`, and `sprint`). If the
Python sidecar stops or disconnects, Godot cancels the current action and
releases those inputs as well. Restarting the sidecar does not bypass the
manual opt-in after an emergency stop.

## Memory

Each normal sidecar start begins with empty memory. Pass `--resume` to load the
previous bounded memory from the Godot user-data directory (or from
`AI_PLAY_DATA_DIR` when explicitly set):

```bash
PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.main --resume
```

Runtime facts and landmarks must originate from observations; stored memory is
context, not authority. Review or remove the local `ai_play/memory.json` file
under the selected data directory when a fresh persisted state is required.

## Privacy and cost

Every decision can send a 768x432 JPEG plus visible prompts and structured
player state to the configured API. This can expose on-screen information and
incur image/token/API charges, so keep camera-image logging off and enable AI
only for an intentional run. Loopback protects the Godot-to-sidecar transport;
it does not prevent the sidecar from sending observations to the configured
external API.

Never place a real key in `.env.example`, source, tests, documentation, commits,
or command arguments. Load it from a local shell as above, or from the ignored
`ai_play/.env` using your own local shell tooling. The program reads environment
variables but does not automatically parse that file. If a key is ever exposed,
revoke and rotate it before another run.

## Credential-free checks

Startup fails before networking when no credential is present:

```bash
env -u AI_PLAY_API_KEY PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.main
```

The automated bridge tests use a fake local agent that returns a single `wait`
action. They exercise loopback hello, observation, response, and disconnect
without contacting any external provider:

```bash
PYTHONPATH=ai_play/src .venv/bin/pytest ai_play/tests -q
```

An actual black-box AI run is opt-in because it sends screenshots and consumes
an external service. Perform it only with a newly rotated operator-supplied key;
do not inspect or seed scenario solutions, and record only transport/action
failures needed for debugging.
