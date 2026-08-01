from copy import deepcopy


PUBLIC_BRIEFING = {
    "game_id": "conveyor_profit",
    "title": "回转食材利润挑战",
    "background": "观察传送带食材和公开菜单，在每个一分钟窗口选择利润更高的一道菜。",
    "objective": "十个窗口结束时，让实际净利润达到各窗口最高单份净利润总和的 80%。",
    "success_condition": "十分钟结束时达到 80% 利润效率目标。",
    "failure_condition": "十分钟结束时低于 80% 利润效率，或达到最大 act 请求数。",
    "rules": [
        "observe 只提供截图和 HUD 级状态；根据画面识别当前食材。",
        "每个一分钟窗口画面中有十六盘真实可选食材，整批恰好能完成两种净利润不同的菜。",
        "从公开菜单计算售价减食材成本；每个窗口只允许一次 make。",
        "合法或非法 make 都会锁定当前窗口；非法组合收入为零并扣除托盘食材成本。",
        "使用 briefing 的公开 menu 核对配方、售价和净利润；再根据截图识别当前食材并比较可行菜。",
        "select_ingredient 使用固定英文食材名；同名食材由游戏从当前画面内随机选择一个。",
        "托盘最多容纳四种食材；收到 tray_full 后先用 undo 撤销托盘最后一种食材再继续。",
        "undo 撤销托盘最后一种食材；make 按当前托盘制作，且必须位于动作批次末尾。",
        "完成后单独调用 wait_next_window；未完成的窗口不能跳过。",
        "每次 act 包含一到三个动作；动作后重新 observe，再依据公开结果继续决策。",
    ],
    "menu": [
        {
            "id": "salad",
            "name": "SALAD",
            "ingredients": ["lettuce", "tomato", "mushroom"],
            "sale_price": 7,
            "net_profit": 3,
        },
        {
            "id": "egg_toast",
            "name": "EGG TOAST",
            "ingredients": ["bread", "egg"],
            "sale_price": 8,
            "net_profit": 4,
        },
        {
            "id": "cheese_toast",
            "name": "CHEESE TOAST",
            "ingredients": ["bread", "cheese"],
            "sale_price": 10,
            "net_profit": 5,
        },
        {
            "id": "burger",
            "name": "BURGER",
            "ingredients": ["bread", "meat", "lettuce", "tomato"],
            "sale_price": 15,
            "net_profit": 6,
        },
        {
            "id": "fish_sandwich",
            "name": "FISH SANDWICH",
            "ingredients": ["bread", "fish", "lettuce"],
            "sale_price": 14,
            "net_profit": 7,
        },
        {
            "id": "mushroom_omelet",
            "name": "MUSHROOM OMELET",
            "ingredients": ["egg", "cheese", "mushroom"],
            "sale_price": 14,
            "net_profit": 7,
        },
    ],
    "ingredient_ids": [
        "lettuce", "tomato", "bread", "egg",
        "mushroom", "cheese", "fish", "meat",
    ],
    "actions": {
        "select_ingredient": {"type": "select_ingredient", "ingredient": "tomato"},
        "undo": {"type": "undo"},
        "make": {"type": "make"},
        "wait_next_window": {"type": "wait_next_window"},
    },
}


def load_conveyor_profit_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
