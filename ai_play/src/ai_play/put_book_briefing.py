"""Approved public briefing for the put_book black-box play session."""

from copy import deepcopy

from .common_briefing_rules import COMMON_CONTROL_RULES
from .reference_image import load_reference_image

PUBLIC_BRIEFING = {
    "game_id": "put_book",
    "title": "整理档案室书籍 / ORGANIZE ARCHIVE BOOKS",
    "background": (
        "这是一个第一人称办公室整理任务。玩家需要读取任务卡，进入档案室，"
        "逐本对准书籍，通过画面中的 HUD 名称找出任务书，并将它们送到 CEO OFFICE。"
    ),
    "objective": (
        "先读取出生点附近的任务卡，进入档案室；逐本对准六本书，只搬运 HUD 名称显示为"
        "任务书的三本书，"
        "严格按低层、中层、高层顺序逐本送到 CEO OFFICE 的青色书籍放置点。"
    ),
    "success_condition": (
        "按低层、中层、高层顺序，将三本经 HUD 名称确认为任务书的书逐本送到 "
        "CEO OFFICE 的书籍放置点。"
    ),
    "failure_condition": (
        "最多允许 150 次 act 请求；达到上限仍未完成任务，或拿起普通书、"
        "顺序错误的任务书时会立即失败。"
    ),
    "rules": COMMON_CONTROL_RULES + [
        "只能依据当前画面、房间文字标识、任务卡内容和动作结果完成任务。",
        "任务卡位于出生点附近并可重复读取。",
        "档案室有六本可搬运的书；书本上方没有悬浮身份标记。",
        (
            "靠近并逐本对准书籍；画面中的交互 HUD 会显示任务书或普通书。"
            "probe_interaction 只负责安全对准，身份需从随后返回的截图中读取。"
        ),
        "先比较三本任务书所在的书架高度，再严格按照低层、中层、高层顺序搬运。",
        (
            "一次搬运一本：将当前书送到 CEO OFFICE 的青色书籍放置点并确认送达后，"
            "再返回搬下一本。"
        ),
        (
            "大厅目标楼梯和 CEO OFFICE 入口带有公开英文标识；"
            "CEO OFFICE 门在本玩法中保持打开。"
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
            "meaning": "可搬运的书需要依据对准时显示的 HUD 名称和书架高度判断是否搬运。",
            "actions": {
                "probe_interaction": "靠近并对准书，再从返回截图的 HUD 名称确认身份。",
                "interact": "按当前提示拿起或放下书。",
                "interact2": "按当前提示拿起或放下书。",
            },
        },
        {
            "id": "book_identity_prompt",
            "meaning": "对准书籍时，画面 HUD 名称会公开显示任务书或普通书。",
            "actions": {
                "look": "读取 HUD 名称，并比较任务书所在书架的高度。",
                "probe_interaction": "安全对准书籍，不会触发拿取或失败。",
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
