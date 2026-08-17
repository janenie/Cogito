"""Approved public briefing for the greet_npc_meeting black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "greet_npc_meeting",
    "title": "先打招呼再去会议室 / GREET, THEN MEET",
    "background": (
        "这是一个第一人称办公室社交与导航任务。办公室里有三名穿不同颜色上衣、持续移动的"
        "同事；玩家需要读取任务卡识别本局联系人，打招呼后跟随对方进入指定会面区域。"
    ),
    "objective": (
        "先读取出生点附近唯一的任务卡，按姓名和可见上衣颜色找到正确联系人。近距离问候后"
        "读取对方告知的会面区域，跟随对方进入会议室；双方到达后从室内关门。"
    ),
    "success_condition": "已问候正确联系人，玩家和联系人都到达本局指定区域，并从会议室内关门。",
    "failure_condition": (
        "第二次问候错误同事会立即失败；同一错误同事只计一次。最多允许 150 次 act 请求，"
        "达到上限仍未完成也会失败。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前画面、房间文字标识、任务卡内容、可见 NPC 和动作结果完成任务。",
        "任务卡位于出生点附近并可重复读取。",
        (
            "三名同事都会移动：蓝衣 H. Voss 沿 MAIN LOBBY—BREAK ROOM—SOFA "
            "巡逻；绿衣 M. Chen 从 CEO OFFICE 门外经过楼梯上层、中段和下层；橙衣 "
            "R. Diaz 沿 CUBICLE AREA—MAIN LOBBY—BREAK ROOM 巡逻。"
        ),
        "需要按任务卡公开的上衣颜色和姓名辨认，不能假设联系人固定在某处。",
        "第一次问候错误同事仍可恢复；第二次问候另一名错误同事会产生正式失败。",
        "看到 NPC 但没有交互提示时，靠近后使用 probe_interaction 调整对准。",
        (
            "正确联系人会在问候后的可见提示中告知 WINDOW SIDE 或 SCREEN SIDE，并开始带路；"
            "沿 MEETING ROOM 文字标牌进入会议室，会议室门开局已打开并解锁。"
        ),
        (
            "玩家和正确联系人必须都到达指定区域，再由玩家转身对准门板或把手关门；"
            "从走廊一侧关门、联系人尚未到场或只进入房间都不会完成任务。"
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
            "meaning": (
                "三名人物穿不同颜色上衣并持续移动；任务卡只指定其中一人为联系人。"
            ),
            "actions": {
                "move": "靠近并跟随视野中的 NPC。",
                "probe_interaction": "对准 NPC 寻找打招呼提示。",
                "interact": "出现提示后执行问候；正确联系人会公开指定区域并开始带路。",
            },
        },
        {
            "id": "operable_door",
            "meaning": (
                "MEETING ROOM 标牌指向目标房间；双方到达联系人告知的区域后，需要从室内关门。"
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
