"""Approved public briefing for the meeting-briefing arrangement scenario."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "arrange_meeting_briefings",
    "title": "会议席位与资料分发",
    "background": (
        "这是一个第一人称办公室关系推理任务。三份会议记录分布在不同区域，"
        "会议室中有四份待分发资料和四个由环境位置区分的席位。"
    ),
    "objective": (
        "先读取入口任务卡，再分别调查 CEO 办公室 (CEO OFFICE)、档案室 (ARCHIVE)"
        "和休息室 (BREAK ROOM) 的会议记录。合并三条关系线索，推断李明、王芳、"
        "陈宇、赵宁的资料应放到会议桌的电视侧 (TV SIDE)、电视对面侧 "
        "(OPPOSITE TV)、会议室门侧 (DOOR SIDE) 和内墙侧 (INNER WALL) 哪个席位；"
        "完成摆放后按 Verify。"
    ),
    "success_condition": "四份资料全部位于正确席位，并按下 Verify。",
    "failure_condition": (
        "Verify 只有一次机会；资料缺失或席位错误会立即失败；最多允许 100 次 act 请求。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "第一步一定要找到并读取出生点附近的任务卡；任务卡可重复阅读。",
        "必须实际前往 CEO 办公室 (CEO OFFICE)、档案室 (ARCHIVE) 和休息室 "
        "(BREAK ROOM) 读取三份会议记录；简报不提供本局线索。",
        "四个席位由电视侧 (TV SIDE)、电视对面侧 (OPPOSITE TV)、会议室门侧 "
        "(DOOR SIDE) 和内墙侧 (INNER WALL) 区分，桌面的 ↻ CLOCKWISE 标记定义顺时针方向。",
        "手持会议资料并对准空席位使用放置交互，资料会自动对齐；一个席位只能容纳一份资料。",
        "已经放好的资料在提交前可以重新拿起并调整，系统不会提前反馈位置是否正确。",
        "只有在四份资料全部摆好并检查无误后才按 Verify；错误或不完整提交会立即结束任务。",
    ],
    "reference_image": (
        "随简报返回的图片只帮助识别常见任务卡、可读记录和交互物，不代表本局线索、"
        "资料答案、席位关系或任何物体位置。"
    ),
    "objects": [
        {
            "id": "task_card_and_records",
            "meaning": "入口任务卡说明规则；三个指定区域的会议记录各提供一条本局线索。",
            "actions": {
                "probe_interaction": "对准任务卡或记录寻找阅读提示。",
                "interact": "阅读并记住规则或关系线索。",
                "close_ui": "关闭阅读界面后继续调查。",
            },
        },
        {
            "id": "meeting_briefing_folders",
            "meaning": "李明、王芳、陈宇、赵宁是四位参会者；会议室内有他们的四份可搬运资料。",
            "actions": {
                "probe_interaction": "对准资料名称和资料本体寻找拿取提示。",
                "interact2": "拿起或放下资料；对准席位时可执行辅助放置。",
            },
        },
        {
            "id": "meeting_seats_and_verify",
            "meaning": "四个席位按环境锚点命名；Verify 会一次性提交当前摆放。",
            "actions": {
                "probe_interaction": "对准席位标记或 Verify 按钮。",
                "interact": "仅在推理和检查完成后按 Verify。",
                "interact2": "手持资料时将其放到空席位。",
            },
        },
    ],
}


def load_arrange_meeting_briefings_briefing():
    return deepcopy(PUBLIC_BRIEFING), load_reference_image()
