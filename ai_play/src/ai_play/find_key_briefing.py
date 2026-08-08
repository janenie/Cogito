"""Approved public briefing for the find_key black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image


PUBLIC_BRIEFING = {
    "game_id": "find_key",
    "title": "董事会合同钥匙 / BOARD CONTRACT KEY",
    "background": (
        "老板不在办公室。董事会将在今天 12:00 审阅一份历时三个月的项目合同，"
        "合同在 12:00 前仍可能修改。办公室内存在多份历史记录、三名知情同事和"
        "六把外观相同的钥匙。"
    ),
    "objective": (
        "调查 CEO OFFICE、MEETING ROOM、CUBICLE AREA 等办公区域，结合日期、"
        "版本、处理人和提交状态，找出今天 12:00 前最后一次正式 SUBMITTED 的版本；"
        "据此解锁 ARCHIVE，并拾取其中的当前合同钥匙。"
    ),
    "success_condition": "解锁档案室并拾取其中的当前合同钥匙。",
    "failure_condition": (
        "最多允许 100 次 act 请求。ARCHIVE 密码只能确认提交一次；密码错误会立即"
        "触发安保锁定并失败。达到请求上限仍未拾取当前合同钥匙也会失败。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前画面、游戏内任务卡、可阅读合同记录、NPC 对话和动作结果推理。",
        "任务卡位于出生点附近，可重复阅读；线索可以按任意顺序调查。",
        "文件名含 FINAL 不代表已经正式提交；必须区分 PREPARED FOR SUBMISSION 与 SUBMITTED。",
        "三名 NPC 都会说真话，但他们给出的密码可能只对应自己处理过的历史版本。",
        "办公室内六把钥匙外观相同，颜色、形状和标签不能区分正确答案。",
        "拿起可见的历史或无关钥匙不会立即失败；必要时可放下并继续调查。",
        "ARCHIVE 密码证据不足时不要确认提交。输入后先阅读不可逆警告；取消不会消耗机会。",
        "正确密码只会打开档案室；必须实际拾取当前合同钥匙才算完成。",
        "看到疑似物体但没有交互提示时，靠近后使用 probe_interaction 调整对准。",
    ],
    "reference_image": (
        "随简报返回的图片只用于识别常见交互物类别，不代表本轮合同、人物、密码、"
        "钥匙位置或正确调查路线。"
    ),
    "objects": [
        {
            "id": "readable_document",
            "meaning": "任务卡和合同记录会显示日期、版本、处理人与流程状态。",
            "actions": {
                "probe_interaction": "对准纸张寻找阅读提示。",
                "interact": "打开并阅读内容。",
                "close_ui": "记住证据后关闭阅读界面。",
            },
        },
        {
            "id": "friendly_npc",
            "meaning": "同事会说明自己处理的合同版本及当时使用的密码。",
            "actions": {
                "probe_interaction": "靠近并对准同事寻找交谈提示。",
                "interact": "交谈并阅读可见回复。",
            },
        },
        {
            "id": "pickup_key",
            "meaning": "六把金色钥匙外观一致，发现位置与合同证据决定其含义。",
            "actions": {
                "probe_interaction": "靠近并对准钥匙确认拾取提示。",
                "interact": "拿起或按当前提示处理钥匙。",
            },
        },
        {
            "id": "keypad",
            "meaning": "ARCHIVE 密码盘只有一次正式提交机会。",
            "actions": {
                "probe_interaction": "对准密码盘寻找使用提示。",
                "interact": "打开密码输入界面。",
                "enter_digits": "输入从证据推导出的四位密码。",
                "close_ui": "确认前可以关闭界面继续调查。",
            },
        },
        {
            "id": "operable_storage",
            "meaning": "抽屉和柜格可能藏有钥匙。",
            "actions": {
                "probe_interaction": "对准把手寻找开关提示。",
                "interact": "打开或关闭收纳空间。",
            },
        },
    ],
}


def load_find_key_briefing():
    return deepcopy(PUBLIC_BRIEFING), load_reference_image()
