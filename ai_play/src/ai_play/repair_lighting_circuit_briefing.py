"""Approved public briefing for the lighting-circuit repair scenario."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "repair_lighting_circuit",
    "title": "未知照明电路修复 / REPAIR LIGHTING CIRCUIT",
    "background": (
        "这是一个第一人称办公室照明诊断任务。入口面板上的 A～D 与四个区域的照明线路"
        "接线未知，其中一条线路已经跳闸。"
    ),
    "objective": (
        "先读取出生点附近唯一的任务卡，记住入口、CEO OFFICE、LOBBY 和 BREAK ROOM"
        "四组灯的目标状态。通过操作 A～D 并往返观察灯光，推断接线和故障线路；"
        "选择一次正确断路器，调整全部灯光后按 Verify。"
    ),
    "success_condition": "正确线路已复位，四组灯全部符合任务卡目标，并按下 Verify。",
    "failure_condition": (
        "断路器只能选择一次，选错立即失败；错误 Verify 立即失败；最多允许 100 次 act 请求。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "第一步一定要找到并读取面板附近的任务卡；任务卡可重复阅读。",
        "A～D 与四个区域是一对一未知接线，不能从字母顺序假设对应关系。",
        "正常线路会让开关指示和对应灯光一起变化；故障线路只改变开关指示，灯光不响应。",
        "面板前不能同时观察所有区域；每次实验后前往各区域观察并记住结果。",
        "断路器按区域命名且整局只能选择一次；选择错误会立即结束任务。",
        "完成复位和灯光调整后才按 Verify；配置错误会立即结束任务。",
    ],
    "reference_image": (
        "随简报返回的图片只帮助识别常见任务卡、开关和交互物，不代表本局映射、"
        "故障线路、目标状态或任何物体位置。"
    ),
    "objects": [
        {
            "id": "readable_document",
            "meaning": "出生点附近任务卡给出四组灯的本局目标状态。",
            "actions": {
                "probe_interaction": "对准任务卡寻找阅读提示。",
                "interact": "阅读并记住四个区域的 ON/OFF 目标。",
                "close_ui": "关闭任务卡后开始面板实验。",
            },
        },
        {
            "id": "lighting_control",
            "meaning": "A～D 控制未知区域线路，开关自身指示状态始终可见。",
            "actions": {
                "probe_interaction": "对准一个控制开关寻找操作提示。",
                "interact": "切换指示状态并观察分散区域中的灯光变化。",
            },
        },
        {
            "id": "breaker_and_verify_buttons",
            "meaning": "区域断路器只能选择一次；Verify 会提交最终配置。",
            "actions": {
                "probe_interaction": "对准带区域文字或 Verify 文字的按钮。",
                "interact": "仅在推断完成后复位线路或提交配置。",
            },
        },
    ],
}


def load_repair_lighting_circuit_briefing():
    return deepcopy(PUBLIC_BRIEFING), load_reference_image()
