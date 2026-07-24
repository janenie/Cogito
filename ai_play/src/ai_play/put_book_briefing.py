"""Approved public briefing for the put_book black-box play session."""

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
    "game_id": "put_book",
    "title": "整理档案室书籍",
    "background": (
        "这是一个第一人称办公室整理任务。玩家需要读取任务卡，进入档案室，"
        "根据当前画面寻找唯一目标书，并把它放入指定纸箱。"
    ),
    "objective": (
        "先读取出生点附近唯一的任务卡，进入档案室，找到场景中唯一可搬运的书，"
        "将它放进档案室地上的目标纸箱。"
    ),
    "success_condition": "目标书进入档案室地上的目标纸箱。",
    "failure_condition": "最多允许 50 次 act 请求；达到上限仍未放好书则失败。",
    "rules": [
        "只能依据当前画面、房间文字标识、任务卡内容和动作结果完成任务。",
        "任务卡位于出生点附近并可重复读取。",
        "目标书可能在高处或低处；必要时使用 jump 或 crouch 调整可达性。",
        "看到疑似目标书但没有交互提示时，靠近后使用 probe_interaction 调整对准。",
        "拿起或放下可搬运物体时，使用当前画面显示的 interact 或 interact2。",
        "只有目标书进入目标纸箱才算完成；仅看到书或纸箱不算成功。",
    ],
    "reference_image": (
        "随简报返回的图片只用于识别常见交互物类别，不代表本局书的位置、"
        "目标箱位置、出生点或正确路线。"
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
            "meaning": "可搬运的书是本局需要整理的目标物。",
            "actions": {
                "probe_interaction": "靠近并对准书确认可用交互。",
                "interact": "按当前提示拿起或放下书。",
                "interact2": "按当前提示拿起或放下书。",
            },
        },
        {
            "id": "cardboard_box",
            "meaning": "档案室地上的纸箱是放置目标书的位置。",
            "actions": {
                "move": "拿着书靠近纸箱。",
                "look": "对准纸箱内部或箱口。",
                "interact": "按当前提示放下正在搬运的书。",
                "interact2": "按当前提示放下正在搬运的书。",
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
