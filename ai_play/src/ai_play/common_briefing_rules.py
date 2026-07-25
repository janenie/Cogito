"""Shared public rules for all AI Play briefings."""

COMMON_CONTROL_RULES = [
    (
        "可以通过 look 多次转动视角来环顾空间，也可以通过前后左右移动在空间中"
        "走动。理论上可以 360 度环顾整个空间，不要只依据初始视野判断。"
    ),
    "look 的单次参数范围是 yaw -45 到 45、pitch -30 到 30；需要大角度转身时连续多次 look。",
    (
        "move 和 sprint 的参数范围是 forward -1 到 1、right -1 到 1、duration_ms "
        "50 到 1000；forward 控制前后，right 控制左右。"
    ),
    "probe_interaction 只用于在当前视野内对准疑似可交互物并小范围扫描交互提示。",
    (
        "probe_interaction 的 target_x 和 target_y 都是截图归一化坐标，范围 0 到 1；"
        "它必须单独作为一个 action batch，且只能在界面关闭时使用。"
    ),
    "每个 act 的 actions 批次必须包含 1 到 3 个动作。",
    "interact、enter_digits、close_ui、stop 等会改变上下文的动作必须放在批次最后。",
    "wait 的 duration_ms 范围是 50 到 2000；不要把 wait 当作默认探索方式。",
    (
        "不要轻易等待；除非视线中出现动态异动的东西，否则应主动观察、转向、靠近、"
        "对准、交互或继续搜索。"
    ),
]
