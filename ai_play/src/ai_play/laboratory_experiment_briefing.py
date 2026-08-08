from __future__ import annotations

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES


PUBLIC_BRIEFING = {
    "game_id": "laboratory_experiment",
    "title": "随机实验室回路 / RANDOM LABORATORY CIRCUIT",
    "background": (
        "这是一个第一人称观察与实验推理任务。每局会给出实验目标、环境和部分条件，"
        "材料分散在实验区域内，正确组合每局可能不同。"
    ),
    "objective": (
        "寻找电池、样本、处理模块和金属棒，将它们带回起点的对应插槽，"
        "用最多三次完整实验推断出满足本局目标的组合。"
    ),
    "success_condition": "组装完整回路并验证，测量结果满足本局公开目标。",
    "failure_condition": "三次完整实验均未成功，或达到 100 次 act 请求上限。",
    "rules": COMMON_CONTROL_RULES + [
        "先阅读左侧 HUD 的目标、环境和两条已知条件。",
        "在附近实验区域寻找三种电池、三种样本、三种处理模块和一根金属棒。",
        "对准材料并触发一次 interact2 拿取，无需持续按住；带到起点对应插槽会自动安装。",
        "把第四种材料装入起点插槽后会自动分析，不需要再对准按钮。",
        "不完整的配置不会消耗机会；完整实验最多三次。",
        "失败后观察电源、电流、稳定性、温度和灯光反馈，再替换单个材料继续推理。",
        "每次交互或实验后直接使用 act 返回的新观察确认 HUD 和插槽状态，不要重复 observe。",
    ],
    "objects": [
        {
            "id": "experiment_materials",
            "meaning": "可携带的电池、样本、处理模块和金属棒，名称与类型在物体上可见。",
            "actions": {"interact2": "对准材料后拿起或放下。"},
        },
        {
            "id": "typed_slots",
            "meaning": "起点有电池、样本、处理和连接件四个插槽，只接受对应类型。",
            "actions": {"move": "手持对应材料靠近插槽以自动安装。"},
        },
        {
            "id": "verification_button",
            "meaning": "四个插槽完整时自动运行实验并把测量反馈显示在 HUD。",
            "actions": {"observe": "读取自动分析后的公开测量反馈。"},
        },
    ],
}


def load_laboratory_experiment_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
