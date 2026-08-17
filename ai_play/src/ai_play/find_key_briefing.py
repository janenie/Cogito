"""Approved public briefing for the find_key black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image


PUBLIC_BRIEFING = {
    "game_id": "find_key",
    "title": "董事会合同钥匙 / BOARD CONTRACT KEY",
    "background": (
        "老板不在办公室。董事会会议将在 12:00 开始，届时将审阅一份历时三个月的"
        "项目合同。合同在会议开始前仍可能修改。办公室内存在多份历史记录、三名知情同事和"
        "六把外观相同的钥匙。"
    ),
    "objective": (
        "调查 CEO OFFICE、MEETING ROOM、CUBICLE AREA 等办公区域，结合日期、"
        "版本、处理人和提交状态，找出董事会会议开始（12:00）前最后一次正式 "
        "SUBMITTED 的合同版本，并确定与该版本对应的正确钥匙。"
    ),
    "success_condition": "根据完整证据，提交与最终签署合同对应的正确钥匙。",
    "failure_condition": (
        "最多允许 150 次 act 请求。提交错误钥匙会触发安保锁定并失败；"
        "达到请求上限仍未提交正确钥匙也会失败。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前画面、游戏内任务卡、可阅读合同记录、NPC 对话和动作结果推理。",
        "任务卡位于出生点附近，可重复阅读；线索可以按任意顺序调查。",
        "文件名含 FINAL 不代表已经正式提交；必须区分 PREPARED FOR SUBMISSION 与 SUBMITTED。",
        "三名 NPC 都会说真话，但他们给出的密码可能只对应自己处理过的历史版本。",
        "办公室内六把钥匙外观相同，颜色、形状和标签不能区分正确答案。",
        "可以观察所有钥匙；对钥匙执行“提交此钥匙”即为最终选择，提交错误会立即失败。",
        "密码输入满四位后会立即验证；密码不对只会显示提示，可以重新输入并继续调查。",
        "密码盘只是调查过程的一部分；必须根据完整证据提交正确钥匙才算完成。",
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
                "probe_interaction": "靠近并对准钥匙寻找最终选择提示。",
                "interact": "提交最终选择；只有证据充分时执行。",
            },
        },
        {
            "id": "keypad",
            "meaning": "密码盘用于验证调查所得的合同凭据。",
            "actions": {
                "probe_interaction": "对准密码盘寻找使用提示。",
                "interact": "打开密码输入界面。",
                "enter_digits": "输入从证据推导出的四位密码；输满后立即验证。",
                "close_ui": "关闭界面并继续调查。",
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
