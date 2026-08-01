"""Approved public briefing for the greet_npc_meeting black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "greet_npc_meeting",
    "title": "先打招呼再去会议室",
    "background": (
        "这是一个第一人称办公室社交与导航任务。玩家需要读取任务卡，找到移动中的 NPC，"
        "完成一次近距离打招呼，然后进入会议室并关上会议室门。"
    ),
    "objective": (
        "先读取出生点附近唯一的任务卡，找到 NPC，在近距离出现交互提示后打招呼。"
        "完成打招呼后，去会议室并把会议室门关上。"
    ),
    "success_condition": "已经和 NPC 打招呼，并在会议室内关上会议室门。",
    "failure_condition": "最多允许 100 次 act 请求；达到上限仍未完成则失败。",
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前画面、房间文字标识、任务卡内容、可见 NPC 和动作结果完成任务。",
        "任务卡位于出生点附近并可重复读取。",
        "NPC 会移动；需要主动观察和寻找，不能假设 NPC 固定在某处。",
        "打招呼必须先完成；没有打招呼前，关上会议室门不会完成任务。",
        "看到 NPC 但没有交互提示时，靠近后使用 probe_interaction 调整对准。",
        "问候成功后沿 MEETING ROOM 文字标牌前往会议室；会议室门开局已打开并解锁。",
        (
            "玩家必须先完整进入会议室，再转身对准门板或把手关门；"
            "从走廊一侧关门或只进入房间都不会完成任务。"
        ),
    ],
    "reference_image": (
        "随简报返回的图片只用于识别常见交互物类别，不代表本局 NPC 位置、"
        "巡逻起点、出生点或正确时机。"
    ),
    "objects": [
        {
            "id": "readable_document",
            "meaning": "纸张或任务卡可以包含本局目标描述。",
            "actions": {
                "probe_interaction": "对准任务卡寻找阅读提示。",
                "interact": "打开并阅读任务内容。",
                "close_ui": "记住目标描述后关闭阅读界面。",
            },
        },
        {
            "id": "moving_npc",
            "meaning": "办公室中的人物可以在足够近并对准时交互；本局必须先和 NPC 打招呼。",
            "actions": {
                "move": "靠近并跟随视野中的 NPC。",
                "probe_interaction": "对准 NPC 寻找打招呼提示。",
                "interact": "出现打招呼提示后执行问候。",
            },
        },
        {
            "id": "operable_door",
            "meaning": (
                "MEETING ROOM 标牌指向目标房间；完成问候后，需要进入房间并从室内关门。"
            ),
            "actions": {
                "probe_interaction": "对准门或把手寻找提示。",
                "interact": "按当前提示打开或关闭门。",
            },
        },
    ],
}


def load_greet_npc_meeting_briefing():
    return deepcopy(PUBLIC_BRIEFING), load_reference_image()
