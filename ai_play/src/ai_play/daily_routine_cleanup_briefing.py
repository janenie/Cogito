from __future__ import annotations

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES


PUBLIC_BRIEFING = {
    "game_id": "daily_routine_cleanup",
    "title": "家庭日常清理与提交",
    "background": (
        "这是一个第一人称家庭日常任务。玩家在一个小型室内空间中探索，"
        "根据 HUD 目标和可见交互提示完成清理。"
    ),
    "objective": (
        "清理屋内 4 个散落垃圾，并检查冰箱里的过期牛奶；把全部 5 个目标物逐个送进"
        "客厅垃圾桶，关好冰箱后点击垃圾桶旁边的完成按钮。"
    ),
    "success_condition": (
        "HUD 显示已扔 5/5、手上为空、冰箱处于关闭状态，并点击完成按钮。"
    ),
    "failure_condition": (
        "任一提交条件尚未满足时点击完成按钮会立即失败；最多允许 150 次 act 请求。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "先观察 HUD 的当前目标、总垃圾数、已扔数量和手上物品。",
        "可交互物体需要靠近、对准并在出现交互提示后操作。",
        "冰箱需要先打开才能取出内部物品；处理完后必须把冰箱关上。",
        "手上一次只能拿一个物品；拿到垃圾后先送到客厅垃圾桶。",
        "只有客厅垃圾桶用于本局目标。",
        (
            "完成按钮在客厅垃圾桶旁边；提交前核对 HUD 已扔 5/5、手上为空和冰箱关闭。"
            "提交失败不会告诉你缺少哪一项条件。"
        ),
        "看到可疑小物体但没有交互提示时，先靠近并使用 probe_interaction 对准它。",
        "每次交互后使用 act 返回的新观察，依据画面、HUD 和动作结果决定下一步。",
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
                "interact": "只有确认所有目标垃圾已处理且冰箱已关闭后再点击。",
            },
        },
        {
            "id": "fridge",
            "meaning": "冰箱可以打开；打开后可以拿取过期牛奶；最终提交前需要关闭。",
            "actions": {
                "probe_interaction": "对准冰箱门寻找打开或拿取提示。",
                "interact": "打开冰箱、拿取过期牛奶，或在取完后关闭冰箱。",
            },
        },
        {
            "id": "loose_trash",
            "meaning": "地面上散落的白色小物体是需要逐个捡起并清理的垃圾。",
            "actions": {
                "probe_interaction": "对准散落垃圾寻找拾取提示。",
                "interact": "拿起垃圾。",
            },
        },
    ],
}


def load_daily_routine_cleanup_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
