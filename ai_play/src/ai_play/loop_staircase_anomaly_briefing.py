from __future__ import annotations

from copy import deepcopy


PUBLIC_BRIEFING = {
    "game_id": "loop_staircase_anomaly",
    "title": "循环楼梯异常 / LOOPING STAIRCASE ANOMALY",
    "background": (
        "这是一个第一人称循环楼梯推理任务。玩家会在五轮观察中循环查看 2F 到 9F；"
        "每轮公开一条新线索，线索顺序每局可能变化。任务是识别唯一符合全部线索的房间，"
        "而不是走到某个真实出口；真正的出口楼层由整局累计线索共同决定。"
    ),
    "objective": (
        "像人类玩家一样观察每层的家具、墙面装饰、可见楼层标牌和其他稳定细节并做好记录；"
        "依据逐轮出现的线索排除错误房间，直到第五轮结束后只剩一个真正出口楼层。"
    ),
    "success_condition": "选择唯一满足五条累计线索的楼层。",
    "failure_condition": (
        "选择错误楼层，或达到最大 act 请求数。"
    ),
    "rules": [
        '使用 act 动作 {"type":"press_key","key":"up"} 切换到下一层。',
        '使用 act 动作 {"type":"press_key","key":"down"} 切换到上一层。',
        '仅在选择当前楼层作为答案时使用 {"type":"press_key","key":"space"}。',
        "本任务不要使用 move 或 sprint；楼层切换只由 Up/Down 键控制。",
        "每轮都要仔细观察 2F 到 9F。",
        "在 9F 按 Up 会返回 2F 并进入下一轮。",
        "一共五轮观察，每轮出现一条新线索。",
        "每局的可见线索顺序可能变化，应读取当前线索，不要背固定脚本。",
        "记录每层可见的家具与物体、墙面装饰和楼层标牌。",
        "跨轮比较记录；部分房间细节可能变化，但相关证据始终受当前线索约束。",
        "根据累计线索维护候选集合，排除与任一线索冲突的楼层。",
        "不要只凭一张截图或当前楼层号下结论。",
        "静态房间外观可能干扰判断，应以线索链为准。",
        "选择错误楼层会立即失败。",
        "每次按键或跨轮后，先使用 act 返回的新观察再决策，不要重复调用 observe。",
    ],
    "objects": [
        {
            "id": "floor_landings",
            "meaning": (
                "每个楼层平台都是候选房间。当前轮次线索直接显示在场景中；房间内的家具、"
                "物体、墙面装饰和楼层标牌需要跨轮记录。"
            ),
            "actions": {
                "observe": (
                    "读取当前线索，检查房间细节，更新本层记录和候选集合，再按 Up 或 Down。"
                ),
            },
        },
        {
            "id": "loop_trigger",
            "meaning": "顶层楼梯触发器会让玩家返回 2F，并推进观察轮次。",
            "actions": {
                "press_key": '观察完 9F 后执行 {"type":"press_key","key":"up"}。',
            },
        },
        {
            "id": "answer_choices",
            "meaning": "2F 到 9F 的最终可选答案。",
            "actions": {
                "press_key": (
                    "使用 Up/Down 显示推断出的真正楼层，再执行 "
                    '{"type":"press_key","key":"space"}。'
                ),
            },
        },
    ],
}


def load_loop_staircase_anomaly_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
