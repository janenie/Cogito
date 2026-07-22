# AI First Play operator guide

AI First Play connects the COGITO Lobby to a local Python sidecar. The Godot
controller is installed in the Lobby but is deliberately disabled at startup;
the operator remains in control of when screenshots begin leaving the game.

## Setup and start

From the repository root, create the environment. If a local `api_key.py`
contains one `OpenAI(...)` call with literal `base_url` and `api_key` strings,
the sidecar reads those two values without executing the file:

```bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
PYTHONPATH=ai_play/src .venv/bin/python -m ai_play.main
```

Environment variables remain the preferred production setup and override the
matching values in `api_key.py`:

```bash
read -rs AI_PLAY_API_KEY
export AI_PLAY_API_KEY
export AI_PLAY_BASE_URL="https://provider.example/v1"
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

`AI_PLAY_API_MAX_RETRIES` controls the OpenAI SDK's bounded exponential retry
behavior. It defaults to `2` and accepts `0` through `5`. Godot remains waiting
and executes no new action while an API request or retry is in progress; after
the final failure, the sidecar returns a safe error response.

## Controls and safety

AI movement is sent through ordinary COGITO input and physics. `interact` and
`interact2` are contextual action slots, not permanent meanings: the current
visible interaction list supplies their prompt and current binding (normally F
and E). The agent may select one only while it appears in that list.

Look `yaw` and `pitch` values are bounded relative mouse-control deltas and do
not guarantee degrees. The player's runtime mouse sensitivity still applies;
the agent confirms the actual turn from `yaw_degrees` and `pitch_degrees` in the
next observation.

Escape is the only physical input that stops an active AI session. The
controller releases held movement (`forward`, `back`, `left`, `right`, and
`sprint`), reports `escape_stop`, and leaves the same Escape event available so
the normal pause menu opens. Other keyboard, mouse, and controller input does
not disable AI. If the Python sidecar stops or disconnects, Godot cancels the
current action and releases held inputs as well.

## Run logs

Each sidecar process creates one timestamped trace under
`~/workspace/cogito_logs` by default. Dots and unsafe path characters in the
model name become underscores:

```text
~/workspace/cogito_logs/
└── gemini-3_5-flash/
    └── 20260721-10-45/
        ├── gemini_godot.jsonl
        └── img/
            ├── 000001.jpg
            └── 000002.jpg
```

Set `AI_PLAY_LOG_ROOT` to choose another root. If a run name already exists, a
numeric suffix such as `-02` prevents overwrite.

The JSONL stream records `model_input`, raw `model_output`,
`decision_validated`, `action_dispatch_requested`, `action_dispatched`, and
`godot_result` events for each `round_idx`. It also records bounded error and
session-stop events. Images are stored once under `img/`; JSONL refers to their
relative paths and never duplicates image base64. A dispatch without a later
Godot result marks an incomplete round after a crash or disconnect.

The sidecar prints the exact run directory at startup. To follow a known run:

```bash
tail -f ~/workspace/cogito_logs/gemini-3_5-flash/20260721-10-45/gemini_godot.jsonl
```

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

Every decision sends a 768x432 JPEG plus visible prompts and structured player
state to the configured API, and the sidecar saves the same JPEG plus the model
request/response trace locally. This can expose on-screen information and incur
image/token/API charges, so enable AI only for an intentional run and protect
the log root accordingly. Loopback protects the Godot-to-sidecar transport; it
does not prevent external API transmission or local trace persistence.

Never place a real key in `.env.example`, tracked source, tests, documentation,
commits, or command arguments. A repository-root `api_key.py` is ignored for
local development, and `ai_play/.env` is also ignored for your own shell
tooling. The program does not automatically parse `.env`. If a key is ever
exposed, revoke and rotate it before another run.

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

An actual black-box AI run is opt-in because it sends screenshots, persists run
traces, and consumes an external service. Perform it only with a newly rotated
operator-supplied key; do not inspect or seed scenario solutions.
