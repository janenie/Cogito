# AI First Play

AI First Play connects the COGITO Lobby to a local Python sidecar. The Godot
controller is installed in the Lobby but is deliberately disabled at startup;
the operator remains in control of when screenshots begin leaving the game.

## AI Play 怎么玩

AI Play 让视觉模型像玩家一样，以“观察一回合、操作一回合”的方式探索
COGITO Lobby。它不是读取关卡答案或直接修改角色坐标，而是反复执行下面的
循环：

1. Godot 截取当前第一人称画面，并提供角色位置、朝向、界面状态和准星下
   当前可用的交互提示。
2. Python sidecar 将这一回合的截图和结构化状态发送给视觉模型。
3. 模型根据当前证据选择 1 到 3 个短动作。
4. Godot 严格校验动作，通过正常输入和物理系统执行，然后把结果交给下一
   回合。
5. 模型查看新截图，确认移动、转向或交互是否成功，再决定下一步。

模型可用的操作范围：

- `look`：小幅转动视角。
- `move` / `sprint`：相对当前视角前后左右移动，单次最长 1 秒。
- `jump` / `crouch`：跳跃或蹲下。
- `probe_interaction`：对准画面中的可疑物体，并在附近小范围寻找交互点。
- `interact`：只有当前观察明确报告 `interact` 或 `interact2` 可用时，才会
  执行对应交互。
- `enter_digits` / `close_ui`：在已打开的数字界面中输入，或关闭界面。
- `wait` / `stop`：等待，或结束控制。

当前默认游戏是 `find_contract`。sidecar 启动时会读取：

- `ai_play/goals/find_contract.py`：中文任务目标、基础规则、成功和失败条件。
- `ai_play/assets/find_contract/assets.json`：11 类视觉资产的系统名、含义和可用
  操作。
- `ai_play/assets/find_contract/imgs/reference_atlas.jpg`：由用户提供截图组成的
  带标签参考图谱。

每回合发送给模型的第一张图片是当前游戏画面，第二张是参考图谱。资产目录包含
线索标志、可搬动杯子、普通门、钥匙、按钮、密码盘、档案室目标门、抽屉、本子、
文件和友好 NPC。目标规则只告诉模型探索、阅读、对话、组合证据并进入档案室，
不会提供密码、线索原文或正确解谜顺序。

`find_contract` 使用
`addons/cogito/AIPlay/ai_play_find_contract_observer.gd`，不会读取或发送生命值
和耐力比例；位置、朝向、平面速度、落地状态、界面与交互提示仍会保留。

交互探索分成两个回合。模型看到按钮、门、抽屉等可疑物体但准星下还没有
交互提示时，会先发送该物体在截图中的归一化坐标。Godot 只转动视角，并在
目标附近最多扫描 9 个位置；这个过程不会自动按 F/E，也不会移动角色。如果
找到交互提示，系统立即截取新画面，下一回合再由模型决定是否执行
`interact`。如果没找到，视角会恢复到探测前的位置，模型可以换目标或继续
探索。

一局默认最多允许 1000 次模型决策请求。一次响应即使包含 3 个动作也只算
1 次，SDK 在同一次请求中的内部重试不重复计数。第 1000 次响应仍会执行：
如果该批动作输入了正确密码，则返回成功；输入了错误密码则立即返回失败；
没有完成解谜则返回 `max_requests` 失败。任意一次完整密码输入错误都会立即
结束本局，不能继续重试。终局时 Godot 会释放所有 AI 输入并停止截图和模型
调用，sidecar 会输出并记录 `correct_password`、`wrong_password` 或
`max_requests`。模型生成文本中的 1 至 6 位独立数字会在 JSONL 和持久化
`memory.json` 中替换为 `[REDACTED]`，包含 `enter_digits` 的工作步骤不会
持久化；当前进程的运行时记忆仍可用于完成本局。终局协议本身也不包含密码。
密码正确、密码错误或达到请求上限后，游戏会显示全屏中文结果并暂停整个场景；
玩家和 AI 都不能继续移动、交互或操作其他界面。

## 快速启动

在仓库根目录准备 `api_key.py`。程序只静态读取其中唯一一个 `OpenAI(...)`
调用里的字面量 `api_key` 和 `base_url`，不会执行这个文件。默认模型是
`gemini-3.5-flash`；需要更换时设置 `AI_PLAY_MODEL`。

首次运行先安装依赖：

```bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
```

终端 1 启动 AI sidecar：

```bash
ai_play/start_ai.sh
```

终端 2 启动允许 AI 控制的 Lobby：

```bash
godot --path . addons/cogito/DemoScenes/COGITO_3_Lobby.tscn -- --ai-play
```

必须带上 `-- --ai-play` 才会启用 AI。运行中按实体键盘 `Escape` 会立即取消
当前动作、释放移动按键并停止 AI；正常启动 Lobby 而不带这个参数时，AI
保持关闭。

## Setup and start

From the repository root, create the environment. If a local `api_key.py`
contains one `OpenAI(...)` call with literal `base_url` and `api_key` strings,
the sidecar reads those two values without executing the file:

```bash
python3 -m venv .venv
.venv/bin/pip install -r ai_play/requirements.txt
ai_play/start_ai.sh
```

Environment variables remain the preferred production setup and override the
matching values in `api_key.py`:

```bash
read -rs AI_PLAY_API_KEY
export AI_PLAY_API_KEY
export AI_PLAY_BASE_URL="https://provider.example/v1"
export AI_PLAY_GAME="find_contract"
export AI_PLAY_MAX_MODEL_REQUESTS=1000
export AI_PLAY_MAX_TOKENS=8192
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
and base64 `image_url` parts; text-only compatibility is insufficient.
`AI_PLAY_GAME` selects the matching goal and asset folder and defaults to
`find_contract`. `AI_PLAY_MAX_MODEL_REQUESTS` sets the decision-request limit,
defaults to `1000`, and accepts values from `1` through `10000`.
`AI_PLAY_MAX_TOKENS` is passed to Chat Completions as `max_tokens`; it defaults
to `8192` so the model has room to reason before returning the required JSON.

`AI_PLAY_API_MAX_RETRIES` controls the OpenAI SDK's bounded exponential retry
behavior. It defaults to `2` and accepts `0` through `5`. Godot remains waiting
and executes no new action while an API request or retry is in progress; after
the final failure, the sidecar returns a safe error response.

## Controls and safety

AI movement is sent through ordinary COGITO input and physics. `interact` and
`interact2` are contextual action slots, not permanent meanings: the current
visible interaction list supplies their prompt and current binding (normally F
and E). The agent may select one only while it appears in that list.

When a visible object looks relevant but no interaction is currently available,
the agent can issue one `probe_interaction` action with normalized screenshot
coordinates. Godot aims through normal mouse input and checks at most nine
nearby crosshair positions within four degrees per axis. The probe never moves
the player and never presses `interact` or `interact2`. An aligned or failed
probe immediately produces a fresh observation, so the model decides in the
next round whether to interact, probe elsewhere, or continue exploring. A
failed probe restores the starting view.

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
`godot_result` events for each `round_idx`. It also records bounded error,
session-stop, and terminal `game_over` events. Images are stored once under
`img/`; JSONL refers to their relative paths and never duplicates image base64.
A dispatch without a later Godot result marks an incomplete round after a crash
or disconnect.

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
This dedicated `memory.json` is stored separately from the timestamped run
log and image directory.

Every model decision includes a `memory_updates` array. New facts, landmarks,
goals, questions, hypotheses, and failures update bounded long-term memory;
when a decision discovers nothing durable, the array stays empty. Separately,
the sidecar automatically records the previous reason, actions, and returned
Godot results in the eight-entry `working_memory`, so recent events do not
depend on the model restating them correctly.

## Privacy and cost

Every decision sends a 768x432 JPEG, the selected game's reference atlas,
visible prompts, and structured player state to the configured API. The
sidecar saves the current JPEG plus the model request/response trace locally;
the tracked reference atlas is logged by path rather than copied per round.
This can expose on-screen information and incur image/token/API charges, so
enable AI only for an intentional run and protect the log root accordingly.
Loopback protects the Godot-to-sidecar transport; it does not prevent external
API transmission or local trace persistence.

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
