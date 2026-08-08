from __future__ import annotations

from copy import deepcopy


PUBLIC_BRIEFING = {
    "game_id": "loop_staircase_anomaly",
    "title": "异常协议 / THE ANOMALY PROTOCOL",
    "background": (
        "这是一个第一人称五轮调查任务。玩家会反复查看 2F 到 9F；"
        "每轮画面只新增一条线索，已经公布的线索会继续保留。"
    ),
    "objective": (
        "逐层观察房间，使用调查板保存历史并维护自己的候选标记；"
        "把每轮新线索与此前画面结合，在第五轮选择唯一符合完整累计证据链的楼层。"
    ),
    "success_condition": "第五轮选择唯一满足完整累计证据链的楼层。",
    "failure_condition": "选择错误楼层，或达到 100 次 act 请求上限。",
    "rules": [
        '使用 {"type":"floor_up"} 切换到下一层，使用 {"type":"floor_down"} 切换到上一层。',
        '房间内移动使用 {"type":"front","step":"small"}、{"type":"back","step":"small"}、{"type":"left","step":"small"} 或 {"type":"right","step":"small"}；step 也可为 large。',
        "small 是 80ms 小步，large 是 180ms 普通步。",
        '使用 {"type":"toggle_board"} 打开或关闭调查板。',
        '调查板打开时，用 {"type":"board_up"}/{"type":"board_down"} 选择楼层行，用 {"type":"toggle_mark"} 切换候选标记。',
        "调查板只保存逐轮画面和手动标记，不会自动比较、计数或判断正误。",
        "每轮观察全部八层后，才可以从 9F 返回 2F 并进入下一轮。",
        '第五轮关闭调查板，用 {"type":"submit_floor"} 提交当前显示的楼层。',
        "每轮读取本轮新线索，并与调查板中的历史画面做跨轮比较。",
        (
            "推荐每次进入房间后使用 look 调整 yaw/pitch 环顾，并在遮挡时向前、后、左、右"
            "（front、back、left、right）小步换位；"
            "部分线索分布在不同墙面和视野盲区，单张初始截图可能无法覆盖"
            "该楼层的全部证据。"
        ),
        "不要使用 move 或 sprint；房间移动、楼层切换和调查板操作必须使用各自的语义 action。",
        "选择错误楼层会立即失败。",
        "每次 action 后先使用 act 返回的新观察再决策，不要重复调用 observe。",
    ],
    "objects": [
        {
            "id": "floor_rooms",
            "meaning": "2F 到 9F 的八个房间；可见细节需要按轮次记录和比较。",
            "actions": {
                "floor_up/floor_down": "切换楼层，观察完成后再继续。",
                "front/back/left/right": "按 small 或 large 步幅在房间内换位观察。",
            },
        },
        {
            "id": "investigation_board",
            "meaning": "保存已观察画面和玩家手动候选标记的调查板，不提供自动分析。",
            "actions": {
                "toggle_board/board_up/board_down/toggle_mark": "开关面板、选择楼层行并维护候选标记。",
            },
        },
        {
            "id": "final_selection",
            "meaning": "第五轮结束后的最终楼层选择。",
            "actions": {
                "submit_floor": "关闭调查板，显示推断楼层后提交。",
            },
        },
    ],
}


def load_loop_staircase_anomaly_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
