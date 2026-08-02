"""Approved public briefing for the find_contract black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "find_contract",
    "title": "寻找合同密码并解锁档案室 / FIND CONTRACT PASSCODE",
    "background": (
        "这是一个第一人称环境解谜任务。玩家需要探索办公场景，调查可见物体，"
        "阅读文件并与友好角色交谈。"
    ),
    "objective": (
        "先读取出生点附近的任务卡，根据任务卡给出的第一处地点开始调查；"
        "严格按记录 1/3、2/3、3/3 的顺序前进，每份当前记录会继续指向下一处地点；"
        "读完三份记录后，按最终记录规定的顺序组合本局六位数字密码并解锁 ARCHIVE。"
    ),
    "success_condition": "正确输入本局密码并解锁 ARCHIVE 档案室。",
    "failure_condition": (
        "最多允许 300 次 act 请求；达到上限仍未解锁 ARCHIVE 则失败。"
        "完成规定调查流程后提交错误密码会立即结束本局。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前游戏画面、可阅读内容、NPC 对话和动作结果推导密码。",
        "每局的出生点、任务卡位置、调查路线、日期、版本号和密码拼接顺序都可能变化。",
        (
            "第一步一定要找到并读取任务卡；在读到任务卡之前，不要开始寻找合同记录、"
            "不要猜测地点顺序，也不要尝试密码。"
        ),
        "任务卡位于出生点附近；它只给出第一处地点，后续地点由当前合同记录逐步公开。",
        "必须依次调查三个地点并按顺序读取三份合同记录。",
        "任务卡和合同记录可以重复读取；提前找到后续记录不会跳过规定的调查顺序。",
        (
            "合同记录可能表现为圆形 COGITO Hint、实体文件或书本；CEO OFFICE 的记录"
            "是桌面文件，BREAK ROOM 的记录是电视柜顶面的实体文件。"
        ),
        "三份记录按顺序给出日期代码（MMDD）、版本代码（VV）和二者的拼接顺序。",
        (
            "读完记录 3/3 后再使用 ARCHIVE 密码盘；证据不全时不要输入，"
            "完成调查后输入错误密码会立即失败。"
        ),
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
            "meaning": "标有 ARCHIVE 的门是本局目标；正确使用旁边的密码盘解锁即成功。",
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
    return deepcopy(PUBLIC_BRIEFING), load_reference_image()
