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
    "failure_condition": "选择错误楼层，或达到最大 act 请求数。",
    "rules": [
        '使用 act 动作 {"type":"press_key","key":"up"} 切换到下一层。',
        '使用 act 动作 {"type":"press_key","key":"down"} 切换到上一层。',
        '使用 act 动作 {"type":"press_key","key":"tab"} 打开或关闭调查板。',
        "调查板打开时，用 Up/Down 选择楼层行，用 Space 切换自己的候选标记。",
        "调查板只保存逐轮画面和手动标记，不会自动比较、计数或判断正误。",
        "调查板关闭时，Up/Down 切换当前房间。",
        "每轮观察全部八层后，才可以从 9F 返回 2F 并进入下一轮。",
        '第五轮关闭调查板，用 {"type":"press_key","key":"space"} 提交当前显示的楼层。',
        "每轮读取本轮新线索，并与调查板中的历史画面做跨轮比较。",
        "不要使用 move 或 sprint；楼层与调查板操作只由按键控制。",
        "选择错误楼层会立即失败。",
        "每次按键后先使用 act 返回的新观察再决策，不要重复调用 observe。",
    ],
    "objects": [
        {
            "id": "floor_rooms",
            "meaning": "2F 到 9F 的八个房间；可见细节需要按轮次记录和比较。",
            "actions": {
                "press_key": "用 Up/Down 切换房间，观察完成后再继续。",
            },
        },
        {
            "id": "investigation_board",
            "meaning": "保存已观察画面和玩家手动候选标记的调查板，不提供自动分析。",
            "actions": {
                "press_key": "用 Tab 开关，板内用 Up/Down 选行、Space 标记。",
            },
        },
        {
            "id": "final_selection",
            "meaning": "第五轮结束后的最终楼层选择。",
            "actions": {
                "press_key": "关闭调查板，显示推断楼层后按 Space 提交。",
            },
        },
    ],
}


def load_loop_staircase_anomaly_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
