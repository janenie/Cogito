"""Approved public briefing for the put_book black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "put_book",
    "title": "整理档案室书籍",
    "background": (
        "这是一个第一人称办公室整理任务。玩家需要读取任务卡，进入档案室，"
        "找出带任务书标记的书，并将它们送到 CEO OFFICE。"
    ),
    "objective": (
        "先读取出生点附近的任务卡，进入档案室；六本书中只搬运三本带任务书标记的书，"
        "严格按低层、中层、高层顺序逐本送到 CEO OFFICE 的青色书籍放置点。"
    ),
    "success_condition": (
        "按低层、中层、高层顺序，将三本带标记的任务书逐本送到 "
        "CEO OFFICE 的书籍放置点。"
    ),
    "failure_condition": (
        "最多允许 150 次 act 请求；达到上限仍未完成任务，或拿起普通书、"
        "顺序错误的任务书时会立即失败。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前画面、房间文字标识、任务卡内容和动作结果完成任务。",
        "任务卡位于出生点附近并可重复读取。",
        "档案室会显示六本可搬运的书，其中三本带有清晰的任务书标记。",
        "先比较三本任务书所在的书架高度，再严格按照低层、中层、高层顺序搬运。",
        (
            "一次搬运一本：将当前书送到 CEO OFFICE 的青色书籍放置点并确认送达后，"
            "再返回搬下一本。"
        ),
        (
            "正确任务书在放置点外提前放下不会完成当前步骤；可以重新拿起并继续送达，"
            "不要因此改拿下一层的书。"
        ),
        "拿起普通书或顺序错误的任务书会立即失败；仅观察或探测交互不会失败。",
        "本任务不要求跳跃或下蹲才能拿到书。",
    ],
    "reference_image": (
        "随简报返回的图片只用于识别常见交互物类别，不代表本局当前布局、"
        "书的位置、出生点或正确路线。"
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
            "id": "carryable_book",
            "meaning": "可搬运的书需要依据任务书标记和书架高度判断是否应当搬运。",
            "actions": {
                "probe_interaction": "靠近并对准书确认可用交互。",
                "interact": "按当前提示拿起或放下书。",
                "interact2": "按当前提示拿起或放下书。",
            },
        },
        {
            "id": "task_book_marker",
            "meaning": "清晰的任务书标记表示这本书属于三本需要按高度顺序搬运的书。",
            "actions": {
                "look": "观察标记并比较任务书所在书架的高度。",
                "probe_interaction": "对准标记附近的书确认交互提示。",
            },
        },
        {
            "id": "ceo_book_placement_point",
            "meaning": "CEO OFFICE 内清晰标出的书籍放置点接收正在搬运的任务书。",
            "actions": {
                "move": "拿着当前任务书靠近 CEO OFFICE 的书籍放置点。",
                "look": "对准书籍放置点。",
                "interact": "按当前提示放置正在搬运的书。",
                "interact2": "按当前提示放置正在搬运的书。",
            },
        },
        {
            "id": "operable_door",
            "meaning": "普通门可以尝试打开，以进入任务区域。",
            "actions": {
                "probe_interaction": "对准门或把手寻找提示。",
                "interact": "按当前提示尝试打开或关闭门。",
            },
        },
    ],
}


def load_put_book_briefing():
    return deepcopy(PUBLIC_BRIEFING), load_reference_image()
