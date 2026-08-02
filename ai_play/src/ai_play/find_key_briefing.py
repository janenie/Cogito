"""Approved public briefing for the find_key black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "find_key",
    "title": "寻找办公室钥匙 / FIND OFFICE KEY",
    "background": (
        "这是一个第一人称办公室空间探索任务。玩家需要观察房间标识、家具和"
        "可交互物体，根据游戏内任务卡寻找目标。"
    ),
    "objective": (
        "先读取出生点附近唯一的任务卡，根据卡片中的环境描述主动探索办公室，"
        "找到并拾取场景中唯一的目标钥匙。"
    ),
    "success_condition": "成功拾取办公室中唯一的目标钥匙。",
    "failure_condition": "最多允许 50 次 act 请求；达到上限仍未拾取钥匙则失败。",
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前画面、房间文字标识、任务卡内容和动作结果寻找钥匙。",
        "任务卡位于出生点附近并可重复读取。",
        "任务卡描述的是环境特征；需要主动探索并理解家具与房间的空间关系。",
        "优先利用 ARCHIVE、MEETING ROOM 等可见房间标牌建立方向，再按线索核对家具。",
        "看到疑似钥匙但没有交互提示时，靠近后使用 probe_interaction 调整对准。",
        "只有成功执行 Pickup 才算完成；仅看到钥匙不算成功。",
        "错误区域和其他拾取物不会直接导致失败；排除一个区域后应换方向搜索，避免原地重复。",
    ],
    "reference_image": (
        "随简报返回的图片只用于识别常见交互物类别，不代表本局钥匙位置、"
        "出生点、任务卡内容或正确路线。"
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
            "id": "pickup_key",
            "meaning": "金色钥匙是可拾取物；本局目标是成功拾取唯一钥匙。",
            "actions": {
                "probe_interaction": "靠近并对准钥匙确认拾取提示。",
                "interact": "出现拾取提示后拿起钥匙。",
            },
        },
        {
            "id": "operable_door",
            "meaning": "普通门可以尝试打开，以进入任务卡描述的办公区域。",
            "actions": {
                "probe_interaction": "对准门或把手寻找提示。",
                "interact": "按当前提示尝试打开或关闭门。",
            },
        },
    ],
}


def load_find_key_briefing():
    return deepcopy(PUBLIC_BRIEFING), load_reference_image()
