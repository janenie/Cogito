from __future__ import annotations

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES


PUBLIC_BRIEFING = {
    "game_id": "garden_watering",
    "title": "花园浇水与下雨警报 / GARDEN WATERING & RAIN ALERT",
    "background": (
        "这是一个第一人称社区花园任务。玩家需要根据房屋和花卉标牌、HUD 时间、"
        "天气与交互提示完成浇水和下雨警报。"
    ),
    "objective": (
        "用广场上的 4 个满水壶，分别浇完向日葵房和绣球花房各 2 块草坪；"
        "下雨时，在雨停前按下兰花房的门铃。"
    ),
    "success_condition": "4 块正确草坪都已浇水，并在下雨期间按过兰花房门铃。",
    "failure_condition": (
        "浇错草坪、按错门铃、非下雨时按兰花房门铃、雨停前未报警，"
        "或达到 150 次 act 请求上限。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "观察 HUD 的游戏时间、天气、水壶状态、浇水进度和警报状态。",
        "向日葵房和绣球花房各有 2 块需要浇水的草坪；不要浇兰花房的草坪。",
        "每个满水壶只能浇 1 块草坪，用完后会消失；回到中央广场拿下一个。",
        "每栋房子都有门铃，但只有下雨期间可以按兰花房门铃。",
        "靠近水壶、草坪或门铃，看到可用交互提示后再执行 interact。",
        "不要越界探索；只在三个房子正面、房屋入口、目标草坪和公共水池/水壶广场之间走路。",
        "天气变为 rain 后优先前往兰花房，在天气恢复前按门铃。",
        "浇水进度达到 4/4 且警报状态显示已按下时任务自动完成，不需要额外 Verify。",
        "每次交互后使用 act 返回的新观察，根据画面、HUD 和动作结果决定下一步。",
    ],
    "objects": [
        {
            "id": "watering_cans",
            "meaning": "中央广场上的 4 个水壶都已装满，每个只能浇 1 块草坪。",
            "actions": {
                "probe_interaction": "靠近并对准一个仍可用的水壶寻找拿取提示。",
                "interact": "靠近水壶并出现提示后拿起。",
            },
        },
        {
            "id": "sunflower_and_hydrangea_lawns",
            "meaning": "向日葵房和绣球花房各有 2 块目标草坪。",
            "actions": {
                "probe_interaction": "手持满水壶时，对准尚未浇过的目标草坪寻找提示。",
                "interact": "手持满水壶并靠近目标草坪时浇水。",
            },
        },
        {
            "id": "orchid_house_doorbell",
            "meaning": "兰花房门铃是下雨警报目标；兰花房草坪不是浇水目标。",
            "actions": {
                "probe_interaction": "靠近并对准兰花房门铃确认按铃提示。",
                "interact": "仅在 HUD 天气显示 rain 时按下门铃。",
            },
        },
    ],
}


def load_garden_watering_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
