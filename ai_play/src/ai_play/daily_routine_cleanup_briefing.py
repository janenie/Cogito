from __future__ import annotations

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES


PUBLIC_BRIEFING = {
    "game_id": "daily_routine_cleanup",
    "title": "清理日常垃圾",
    "background": (
        "这是一个第一人称家庭日常任务。玩家在一个小型室内空间中探索，"
        "根据 HUD 目标和可见交互提示完成清理。"
    ),
    "objective": (
        "把家里全部需要处理的垃圾都扔进客厅垃圾桶，然后点击客厅垃圾桶旁边的完成按钮。备注：冰箱里有一盒喝完的牛奶。"
    ),
    "success_condition": "所有目标垃圾都已扔进客厅垃圾桶，并点击完成按钮。",
    "failure_condition": "在垃圾尚未全部处理时点击完成按钮，或达到最大 act 请求数。",
    "rules": COMMON_CONTROL_RULES + [
        "先观察 HUD 的当前目标、总垃圾数、已扔数量和手上物品。",
        "可交互物体需要靠近、对准并在出现交互提示后操作。",
        "冰箱需要先打开，才能取牛奶",
        "手上一次只能拿一个物品；拿到垃圾后先送到客厅垃圾桶。",
        "只有客厅垃圾桶用于本局目标。",
        "完成按钮在客厅垃圾桶旁边；垃圾未清理完时点击会失败。",
        "看到可疑小物体但没有交互提示时，先靠近并使用 probe_interaction 对准它。",
        "每次交互后重新 observe，依据画面、HUD 和动作结果决定下一步。",
    ],
    "objects": [
        {
            "id": "living_room_trash_bin",
            "meaning": "客厅垃圾桶是所有垃圾的投放目标。",
            "actions": {
                "probe_interaction": "对准垃圾桶寻找使用提示。",
                "interact": "手上有垃圾时，把垃圾扔进桶里。",
            },
        },
        {
            "id": "finish_button",
            "meaning": "完成按钮用于提交任务。",
            "actions": {
                "probe_interaction": "对准按钮寻找完成任务提示。",
                "interact": "只有确认所有垃圾已处理后再点击。",
            },
        },
        {
            "id": "fridge",
            "meaning": "冰箱可以打开；打开后可能出现牛奶。",
            "actions": {
                "probe_interaction": "对准冰箱门寻找打开或拿取提示。",
                "interact": "打开冰箱或拿取牛奶。",
            },
        },
        {
            "id": "loose_trash",
            "meaning": "地上的白色物体是垃圾。你看到垃圾需要捡起的垃圾。",
            "actions": {
                "probe_interaction": "对准散落垃圾寻找拾取提示。",
                "interact": "拿起垃圾。",
            },
        },
    ],
}


def load_daily_routine_cleanup_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
