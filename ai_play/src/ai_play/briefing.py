"""Approved public briefing for the find_contract black-box play session."""

from copy import deepcopy
from pathlib import Path


MAX_REFERENCE_IMAGE_BYTES = 2 * 1024 * 1024
REFERENCE_IMAGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "assets"
    / "find_contract"
    / "imgs"
    / "reference_atlas.jpg"
)

PUBLIC_BRIEFING = {
    "game_id": "find_contract",
    "title": "寻找合同密码并进入档案室",
    "background": (
        "这是一个第一人称环境解谜游戏。玩家需要探索办公场景，调查可见物体，"
        "阅读文件并与友好角色交谈。"
    ),
    "objective": (
        "从本局可见线索和对话中推导出可靠的数字密码，解锁并进入标有 "
        "ARCHIVE 的档案室。"
    ),
    "success_condition": "正确解锁 ARCHIVE 档案室并进入。",
    "failure_condition": "提交错误密码会立即结束本局。",
    "rules": [
        "只能依据当前游戏画面、可阅读内容、NPC 对话和动作结果推导密码。",
        "线索可能分散在多个房间和不同交互对象上，需要探索、记录并组合信息。",
        "看到疑似可交互物但没有交互提示时，先靠近并使用 probe_interaction 对准它。",
        "交互完成后重新观察画面，再决定下一步动作。",
        "密码证据不足时继续寻找线索，不要盲猜或反复试错。",
        "普通门、抽屉、拾取物和按钮可能用于通行或调查，也可能与主谜题无关。",
    ],
    "reference_image": (
        "随简报返回的图片是物体类别参考图，只用于识别常见可交互物体，"
        "不代表当前位置、当前状态、线索原文、密码或正确解谜顺序。"
    ),
    "objects": [
        {
            "id": "clue_hint",
            "meaning": "悬浮旋转的 COGITO 标志表示附近有可阅读的信息。",
            "actions": {
                "probe_interaction": "对准标志寻找当前可用的阅读交互。",
                "interact": "出现阅读提示后打开内容。",
                "close_ui": "记住有用信息后关闭阅读界面。",
            },
        },
        {
            "id": "carryable_cup",
            "meaning": "杯子等物理道具可以拿起、移动或放下，但不一定与谜题有关。",
            "actions": {
                "probe_interaction": "对准物体确认是否存在交互。",
                "interact": "按当前提示拿起、移动或放下物体。",
            },
        },
        {
            "id": "operable_door",
            "meaning": "普通门或门把手可以尝试开关；锁住时应寻找其他解锁方式。",
            "actions": {
                "probe_interaction": "对准门板或门把手寻找提示。",
                "interact": "按当前提示尝试打开或关闭门。",
            },
        },
        {
            "id": "pickup_key",
            "meaning": "钥匙是可拾取物，可能用于解锁某扇门。",
            "actions": {
                "probe_interaction": "对准钥匙确认拾取交互。",
                "interact": "出现拾取提示后拿起钥匙。",
            },
        },
        {
            "id": "elevator_button",
            "meaning": "红色按钮可能触发升降平台、电梯或其他机关。",
            "actions": {
                "probe_interaction": "对准按钮寻找按下提示。",
                "interact": "按下按钮后重新观察环境变化。",
            },
        },
        {
            "id": "keypad",
            "meaning": "密码盘用于输入从游戏内线索推导出的数字密码。",
            "actions": {
                "probe_interaction": "对准密码盘寻找使用提示。",
                "interact": "打开密码输入界面。",
                "enter_digits": "仅在证据充分时输入一至六位数字。",
                "close_ui": "关闭界面并继续寻找线索。",
            },
        },
        {
            "id": "archive_goal_door",
            "meaning": "标有 ARCHIVE 的门是本局目标，需要先解锁再打开并进入。",
            "actions": {
                "probe_interaction": "对准门或门把手确认状态。",
                "interact": "解锁后打开门并进入档案室。",
            },
        },
        {
            "id": "operable_drawer",
            "meaning": "带把手的抽屉可以打开，内部或附近可能有物品或信息。",
            "actions": {
                "probe_interaction": "对准抽屉把手寻找提示。",
                "interact": "打开抽屉并观察内部。",
            },
        },
        {
            "id": "readable_notebook",
            "meaning": "本子和笔记等可阅读物可能包含线索。",
            "actions": {
                "probe_interaction": "对准本子寻找阅读提示。",
                "interact": "打开并阅读内容。",
                "close_ui": "记录关键信息后关闭阅读界面。",
            },
        },
        {
            "id": "readable_document",
            "meaning": "纸张、文件或合同等可阅读物可能包含线索。",
            "actions": {
                "probe_interaction": "对准文件寻找阅读提示。",
                "interact": "打开并阅读内容。",
                "close_ui": "记录关键信息后关闭阅读界面。",
            },
        },
        {
            "id": "friendly_npc",
            "meaning": "友好角色可以对话，可能提供线索或指出值得调查的地点。",
            "actions": {
                "probe_interaction": "靠近角色并对准其身体寻找对话提示。",
                "interact": "出现提示后交谈并观察回复。",
                "close_ui": "记住有用信息后退出对话界面。",
            },
        },
    ],
}


def load_public_briefing():
    """Return a fresh public briefing and its bounded JPEG reference image."""
    try:
        image_bytes = REFERENCE_IMAGE_PATH.read_bytes()
    except OSError as error:
        raise RuntimeError("briefing_reference_image_unavailable") from error
    if (
        len(image_bytes) > MAX_REFERENCE_IMAGE_BYTES
        or not image_bytes.startswith(b"\xff\xd8\xff")
        or not image_bytes.endswith(b"\xff\xd9")
    ):
        raise RuntimeError("briefing_reference_image_invalid")
    return deepcopy(PUBLIC_BRIEFING), image_bytes
