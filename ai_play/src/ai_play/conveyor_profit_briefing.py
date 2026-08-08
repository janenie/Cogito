from copy import deepcopy


PUBLIC_BRIEFING = {
    "game_id": "conveyor_profit",
    "title": "回转食材利润挑战 / CONVEYOR PROFIT CHALLENGE",
    "background": (
        "像人类玩家一样观察传送带、固定公开菜单、当前需求倍率和市场线索。"
        "不要只按基础价格选择；逐项核对当前画面是否具有一道菜要求的每份食材，"
        "并结合配方次数与下一轮预告规划。"
    ),
    "objective": (
        "完成十个一分钟窗口，满足 observation.conveyor.contracts 中的分类合同，并让包含"
        "合同奖惩的实际净利润达到隐藏在线基准的 90%。"
    ),
    "success_condition": "十分钟结束时达到 90% 隐藏在线基准效率目标。",
    "failure_condition": "十分钟结束时低于 90% 隐藏在线基准，或达到 100 次 act 请求上限。",
    "rules": [
        "observe 只提供截图和 HUD 级状态；根据画面识别当前窗口的十六盘食材。",
        "每个一分钟窗口只能提交一次 make；配方必须严格包含菜单列出的全部且仅有的食材。",
        "market.category_multipliers 给出本轮五类菜品的精确当前需求倍率；菜单售价是基础售价，实际售价按基础售价乘倍率并四舍五入，食材成本不变。",
        "每次 observe 从 conveyor.market.signals 读取本轮公开的下一轮涨跌线索。前九轮各有两条；两条线索可能互相强化，也可能冲突，需要从事件规模判断力度。第十轮没有下一轮线索。",
        "同一道菜整局最多成功制作两次；根据每次 accepted 收据自行记录已成功制作次数。",
        (
            "每局有三份公开分类合同，分别在第 3、6、10 窗截止。每次 observe 都从 "
            "conveyor.contracts 读取精确要求、奖励、违约金和 active/completed/missed 状态；"
            "不同市场脚本的目标类别或数量可能不同。"
        ),
        (
            "合同只统计截止前 accepted 菜品的类别；奖励或违约金在截止窗口结束时进入 "
            "conveyor.net_profit。根据 accepted 收据自行记录已完成类别，提前兼顾合同和利润。"
        ),
        "第三次提交配方正确但次数已满的菜会返回 recipe_limit_exceeded：收入为零、扣除托盘食材成本并锁定窗口。",
        "非法组合返回 invalid_combo：收入为零、扣除托盘食材成本并锁定窗口。",
        "select_ingredient 使用 ingredient_ids 中的固定英文材料名；同名食材由游戏从当前画面内随机选择一个。",
        "食材一旦选入托盘就不可撤销；选错时只能用 make 提交，错误组合会消耗全部托盘食材并锁定本轮。",
        "窗口到期时，尚未提交的托盘食材同样会被报废并计入成本。",
        "托盘最多容纳五份食材；收到 tray_full 后不能继续选材，只能用 make 结算当前托盘。",
        "make 按当前托盘制作，且必须位于动作批次末尾。",
        "完成后单独调用 wait_next_window；未完成的窗口不能跳过，跨过截止点会立即结算合同。",
        "每次 act 包含一到三个动作；直接使用 act 返回的新观察，依据截图变化和公开结果继续决策。",
    ],
    "menu": [
        {
            "id": "garden_salad",
            "name": "GARDEN SALAD",
            "ingredients": ["lettuce", "tomato", "carrot"],
            "sale_price": 7,
            "net_profit": 4,
        },
        {
            "id": "avocado_salad",
            "name": "AVOCADO SALAD",
            "ingredients": ["lettuce", "tomato", "avocado"],
            "sale_price": 19,
            "net_profit": 13,
        },
        {
            "id": "carrot_sausage_soup",
            "name": "CARROT SAUSAGE SOUP",
            "ingredients": ["sausage", "mushroom", "onion", "carrot"],
            "sale_price": 14,
            "net_profit": 6,
        },
        {
            "id": "pumpkin_sausage_soup",
            "name": "PUMPKIN SAUSAGE SOUP",
            "ingredients": ["sausage", "mushroom", "onion", "pumpkin"],
            "sale_price": 24,
            "net_profit": 15,
        },
        {
            "id": "classic_burger",
            "name": "CLASSIC BURGER",
            "ingredients": ["bread", "meat", "lettuce", "tomato"],
            "sale_price": 17,
            "net_profit": 8,
        },
        {
            "id": "avocado_burger",
            "name": "AVOCADO BURGER",
            "ingredients": ["bread", "meat", "avocado", "tomato"],
            "sale_price": 30,
            "net_profit": 18,
        },
        {
            "id": "broccoli_bacon_omelet",
            "name": "BROCCOLI BACON OMELET",
            "ingredients": ["egg", "cheese", "bacon", "broccoli"],
            "sale_price": 18,
            "net_profit": 7,
        },
        {
            "id": "corn_bacon_omelet",
            "name": "CORN BACON OMELET",
            "ingredients": ["egg", "cheese", "bacon", "corn"],
            "sale_price": 27,
            "net_profit": 16,
        },
        {
            "id": "garden_fish_sandwich",
            "name": "GARDEN FISH SANDWICH",
            "ingredients": ["bread", "fish", "lettuce", "onion"],
            "sale_price": 15,
            "net_profit": 7,
        },
        {
            "id": "avocado_fish_sandwich",
            "name": "AVOCADO FISH SANDWICH",
            "ingredients": ["bread", "fish", "avocado", "onion"],
            "sale_price": 28,
            "net_profit": 17,
        },
    ],
    "ingredient_ids": [
        "lettuce", "tomato", "carrot", "avocado", "sausage", "mushroom",
        "onion", "pumpkin", "bread", "meat", "egg", "cheese", "bacon",
        "broccoli", "corn", "fish",
    ],
    "category_ids": ["salad", "soup", "burger", "omelet", "sandwich"],
    "ingredient_costs": {
        "lettuce": 1,
        "tomato": 1,
        "carrot": 1,
        "onion": 1,
        "bread": 2,
        "egg": 2,
        "mushroom": 2,
        "pumpkin": 2,
        "broccoli": 2,
        "corn": 2,
        "cheese": 3,
        "avocado": 4,
        "sausage": 4,
        "bacon": 4,
        "fish": 4,
        "meat": 5,
    },
    "actions": {
        "select_ingredient": {"type": "select_ingredient", "ingredient": "tomato"},
        "make": {"type": "make"},
        "wait_next_window": {"type": "wait_next_window"},
    },
}


def load_conveyor_profit_briefing():
    return deepcopy(PUBLIC_BRIEFING), None
