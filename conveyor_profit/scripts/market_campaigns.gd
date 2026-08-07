class_name MarketCampaigns
extends RefCounted

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const ECONOMY := preload("res://conveyor_profit/scripts/market_economy.gd")
const TARGET_RATIO: float = 0.9

const NORMAL := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
const SALAD_HIGH := {"salad": 1.25, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
const SALAD_BOOM := {"salad": 1.5, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
const SALAD_LOW := {"salad": 0.75, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
const SOUP_HIGH := {"salad": 1.0, "soup": 1.25, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
const SOUP_BOOM := {"salad": 1.0, "soup": 1.5, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
const SOUP_LOW := {"salad": 1.0, "soup": 0.75, "burger": 1.0, "omelet": 1.0, "sandwich": 1.0}
const BURGER_HIGH := {"salad": 1.0, "soup": 1.0, "burger": 1.25, "omelet": 1.0, "sandwich": 1.0}
const BURGER_BOOM := {"salad": 1.0, "soup": 1.0, "burger": 1.5, "omelet": 1.0, "sandwich": 1.0}
const BURGER_LOW := {"salad": 1.0, "soup": 1.0, "burger": 0.75, "omelet": 1.0, "sandwich": 1.0}
const OMELET_HIGH := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.25, "sandwich": 1.0}
const OMELET_BOOM := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.5, "sandwich": 1.0}
const OMELET_LOW := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 0.75, "sandwich": 1.0}
const SANDWICH_HIGH := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.25}
const SANDWICH_BOOM := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 1.5}
const SANDWICH_LOW := {"salad": 1.0, "soup": 1.0, "burger": 1.0, "omelet": 1.0, "sandwich": 0.75}

const A3 := {"salad": 1.0, "soup": 1.25, "burger": 0.75, "omelet": 1.0, "sandwich": 1.0}
const A4 := {"salad": 0.75, "soup": 1.0, "burger": 1.0, "omelet": 1.25, "sandwich": 1.0}
const A5 := {"salad": 1.0, "soup": 1.0, "burger": 1.25, "omelet": 0.75, "sandwich": 1.0}
const A6 := {"salad": 1.0, "soup": 0.75, "burger": 1.0, "omelet": 1.0, "sandwich": 1.25}
const A7 := {"salad": 1.5, "soup": 1.0, "burger": 1.0, "omelet": 0.75, "sandwich": 1.0}
const A8 := {"salad": 1.0, "soup": 0.75, "burger": 1.5, "omelet": 1.0, "sandwich": 1.0}
const A10 := {"salad": 1.0, "soup": 1.5, "burger": 1.0, "omelet": 1.0, "sandwich": 1.5}

const CAMPAIGNS: Array[Dictionary] = [
	{
		"id": "A", "strategy": "history_quota", "rounds": [
			{"candidate_recipe_ids": ["avocado_burger", "classic_burger", "garden_salad"], "category_multipliers": NORMAL, "signals": [{"category": "burger", "direction": "up", "text": "中型球赛即将散场，下一轮汉堡需求可能升高。"}, {"category": "burger", "direction": "down", "text": "末班车延误，下一轮汉堡需求可能降低。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["avocado_burger", "avocado_salad", "carrot_sausage_soup"], "category_multipliers": NORMAL, "signals": [{"category": "soup", "direction": "up", "text": "强冷空气抵达，下一轮汤类需求可能升高。"}, {"category": "burger", "direction": "down", "text": "体育活动取消，下一轮汉堡需求可能降低。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "avocado_fish_sandwich", "classic_burger"], "category_multipliers": A3, "signals": [{"category": "omelet", "direction": "up", "text": "商务区早班人数增加，下一轮煎蛋卷需求可能升高。"}, {"category": "salad", "direction": "down", "text": "健康讲座取消，下一轮沙拉需求可能降低。"}], "baseline_recipe_id": "pumpkin_sausage_soup"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "avocado_salad", "garden_fish_sandwich"], "category_multipliers": A4, "signals": [{"category": "burger", "direction": "up", "text": "万人球赛即将散场，下一轮汉堡需求可能升高。"}, {"category": "omelet", "direction": "down", "text": "早餐客流结束，下一轮煎蛋卷需求可能降低。"}], "baseline_recipe_id": "corn_bacon_omelet"},
			{"candidate_recipe_ids": ["avocado_burger", "avocado_fish_sandwich", "broccoli_bacon_omelet"], "category_multipliers": A5, "signals": [{"category": "sandwich", "direction": "up", "text": "渡轮乘客滞留，下一轮三明治需求可能升高。"}, {"category": "soup", "direction": "down", "text": "气温回暖，下一轮汤类需求可能降低。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "pumpkin_sausage_soup", "corn_bacon_omelet"], "category_multipliers": A6, "signals": [{"category": "salad", "direction": "up", "text": "大型健康展进入午餐时段，下一轮沙拉需求可能大幅升高。"}, {"category": "omelet", "direction": "down", "text": "早班人群离场，下一轮煎蛋卷需求可能降低。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_salad", "corn_bacon_omelet", "pumpkin_sausage_soup"], "category_multipliers": A7, "signals": [{"category": "burger", "direction": "up", "text": "两万人冠军赛即将散场，下一轮汉堡需求可能大幅升高。"}, {"category": "soup", "direction": "down", "text": "附近供暖恢复，下一轮汤类需求可能降低。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["avocado_burger", "corn_bacon_omelet", "pumpkin_sausage_soup"], "category_multipliers": A8, "signals": [{"category": "burger", "direction": "up", "text": "夜场比赛满座，下一轮汉堡需求可能继续升高。"}, {"category": "burger", "direction": "up", "text": "场外餐车停业，下一轮汉堡需求可能进一步升高。"}], "baseline_recipe_id": "corn_bacon_omelet"},
			{"candidate_recipe_ids": ["avocado_burger", "carrot_sausage_soup", "broccoli_bacon_omelet"], "category_multipliers": BURGER_BOOM, "signals": [{"category": "soup", "direction": "up", "text": "暴雨降温，下一轮汤类需求可能大幅升高。"}, {"category": "sandwich", "direction": "up", "text": "铁路晚点，下一轮三明治需求可能大幅升高。"}], "baseline_recipe_id": "broccoli_bacon_omelet"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "corn_bacon_omelet", "garden_fish_sandwich"], "category_multipliers": A10, "signals": [], "baseline_recipe_id": "pumpkin_sausage_soup"},
		]
	},
	{
		"id": "B", "strategy": "stacked_signals", "rounds": [
			{"candidate_recipe_ids": ["corn_bacon_omelet", "broccoli_bacon_omelet", "garden_salad"], "category_multipliers": NORMAL, "signals": [{"category": "salad", "direction": "up", "text": "三千人健康展进入午餐时段，下一轮沙拉需求可能升高。"}, {"category": "salad", "direction": "up", "text": "附近健身中心举行团体活动，下一轮沙拉需求可能升高。"}], "baseline_recipe_id": "corn_bacon_omelet"},
			{"candidate_recipe_ids": ["avocado_salad", "avocado_burger", "carrot_sausage_soup"], "category_multipliers": SALAD_HIGH, "signals": [{"category": "soup", "direction": "up", "text": "强冷空气伴随降雨，下一轮汤类需求可能升高。"}, {"category": "soup", "direction": "up", "text": "办公区增加夜班，下一轮热汤需求可能升高。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "avocado_fish_sandwich", "classic_burger"], "category_multipliers": SOUP_HIGH, "signals": [{"category": "omelet", "direction": "up", "text": "大型工厂提前换班，下一轮煎蛋卷需求可能升高。"}, {"category": "omelet", "direction": "up", "text": "车站早餐店临时停业，下一轮煎蛋卷需求可能升高。"}], "baseline_recipe_id": "pumpkin_sausage_soup"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "avocado_salad", "garden_fish_sandwich"], "category_multipliers": OMELET_BOOM, "signals": [{"category": "omelet", "direction": "up", "text": "工厂早班继续扩充，下一轮煎蛋卷需求可能保持高位。"}, {"category": "omelet", "direction": "up", "text": "学校举办早餐活动，下一轮煎蛋卷需求可能继续升高。"}], "baseline_recipe_id": "corn_bacon_omelet"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "pumpkin_sausage_soup", "avocado_burger"], "category_multipliers": OMELET_BOOM, "signals": [{"category": "burger", "direction": "down", "text": "体育馆比赛取消，下一轮汉堡需求可能降低。"}, {"category": "burger", "direction": "down", "text": "道路施工分流观众，下一轮汉堡需求可能进一步降低。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["avocado_burger", "avocado_salad", "broccoli_bacon_omelet"], "category_multipliers": BURGER_LOW, "signals": [{"category": "sandwich", "direction": "up", "text": "铁路晚点，大量乘客需要便携食品，下一轮三明治需求可能升高。"}, {"category": "sandwich", "direction": "up", "text": "大型会议追加盒餐，下一轮三明治需求可能升高。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "pumpkin_sausage_soup", "classic_burger"], "category_multipliers": SANDWICH_BOOM, "signals": [{"category": "sandwich", "direction": "up", "text": "会议临时延长，下一轮三明治需求可能保持高位。"}, {"category": "sandwich", "direction": "up", "text": "车站餐厅关闭，下一轮三明治需求可能继续升高。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "avocado_burger", "carrot_sausage_soup"], "category_multipliers": SANDWICH_BOOM, "signals": [{"category": "salad", "direction": "down", "text": "健康展迁往其他城区，下一轮沙拉需求可能降低。"}, {"category": "salad", "direction": "down", "text": "暴雨取消户外健身活动，下一轮沙拉需求可能进一步降低。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "garden_salad", "classic_burger"], "category_multipliers": SALAD_LOW, "signals": [{"category": "soup", "direction": "up", "text": "暴雪预警导致气温骤降，下一轮汤类需求可能升高。"}, {"category": "soup", "direction": "up", "text": "夜班单位发放热食补贴，下一轮汤类需求可能升高。"}], "baseline_recipe_id": "classic_burger"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "avocado_burger", "broccoli_bacon_omelet"], "category_multipliers": SOUP_BOOM, "signals": [], "baseline_recipe_id": "pumpkin_sausage_soup"},
		]
	},
	{
		"id": "C", "strategy": "conflicting_signals", "rounds": [
			{"candidate_recipe_ids": ["avocado_burger", "pumpkin_sausage_soup", "garden_salad"], "category_multipliers": NORMAL, "signals": [{"category": "burger", "direction": "up", "text": "两万人比赛即将散场，下一轮汉堡需求可能升高。"}, {"category": "burger", "direction": "down", "text": "附近道路局部施工，下一轮汉堡需求可能降低。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["avocado_burger", "corn_bacon_omelet", "avocado_salad"], "category_multipliers": BURGER_HIGH, "signals": [{"category": "soup", "direction": "up", "text": "强冷空气抵达，下一轮汤类需求可能升高。"}, {"category": "soup", "direction": "down", "text": "部分办公楼恢复供暖，下一轮汤类需求可能降低。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "avocado_fish_sandwich", "classic_burger"], "category_multipliers": SOUP_HIGH, "signals": [{"category": "omelet", "direction": "up", "text": "工厂增加早班，下一轮煎蛋卷需求可能升高。"}, {"category": "omelet", "direction": "down", "text": "首班通勤列车取消，下一轮煎蛋卷需求可能降低。"}], "baseline_recipe_id": "pumpkin_sausage_soup"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "avocado_salad", "classic_burger"], "category_multipliers": OMELET_LOW, "signals": [{"category": "sandwich", "direction": "up", "text": "大范围铁路晚点，下一轮三明治需求可能升高。"}, {"category": "sandwich", "direction": "down", "text": "车站一家食品店恢复营业，下一轮三明治需求可能降低。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "corn_bacon_omelet", "garden_salad"], "category_multipliers": SANDWICH_HIGH, "signals": [{"category": "salad", "direction": "up", "text": "五千人健康展开放，下一轮沙拉需求可能升高。"}, {"category": "salad", "direction": "down", "text": "小范围降雨可能减少客流，下一轮沙拉需求可能降低。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_salad", "carrot_sausage_soup", "broccoli_bacon_omelet"], "category_multipliers": SALAD_HIGH, "signals": [{"category": "burger", "direction": "down", "text": "体育馆比赛临时取消，下一轮汉堡需求可能降低。"}, {"category": "burger", "direction": "up", "text": "附近小型演出即将结束，下一轮汉堡需求可能升高。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["avocado_burger", "corn_bacon_omelet", "garden_fish_sandwich"], "category_multipliers": BURGER_LOW, "signals": [{"category": "soup", "direction": "up", "text": "局部阵雨，下一轮汤类需求可能升高。"}, {"category": "soup", "direction": "down", "text": "全城高温预警，下一轮汤类需求可能降低。"}], "baseline_recipe_id": "corn_bacon_omelet"},
			{"candidate_recipe_ids": ["carrot_sausage_soup", "avocado_fish_sandwich", "broccoli_bacon_omelet"], "category_multipliers": SOUP_LOW, "signals": [{"category": "omelet", "direction": "up", "text": "学校启动大型早餐计划，下一轮煎蛋卷需求可能升高。"}, {"category": "omelet", "direction": "down", "text": "一家办公楼推迟早班，下一轮煎蛋卷需求可能降低。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "avocado_burger", "garden_salad"], "category_multipliers": OMELET_HIGH, "signals": [{"category": "sandwich", "direction": "down", "text": "通勤罢工减少车站客流，下一轮三明治需求可能降低。"}, {"category": "sandwich", "direction": "up", "text": "小型徒步团需要便携食品，下一轮三明治需求可能升高。"}], "baseline_recipe_id": "corn_bacon_omelet"},
			{"candidate_recipe_ids": ["garden_fish_sandwich", "avocado_burger", "classic_burger"], "category_multipliers": SANDWICH_LOW, "signals": [], "baseline_recipe_id": "classic_burger"},
		]
	},
	{
		"id": "D", "strategy": "standard_substitutes", "rounds": [
			{"candidate_recipe_ids": ["avocado_salad", "pumpkin_sausage_soup", "classic_burger"], "category_multipliers": NORMAL, "signals": [{"category": "sandwich", "direction": "up", "text": "大型会议增加订单，下一轮三明治需求可能升高。"}, {"category": "sandwich", "direction": "down", "text": "会议启用内部餐饮，下一轮公共三明治需求可能降低。"}], "baseline_recipe_id": "pumpkin_sausage_soup"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "avocado_fish_sandwich", "broccoli_bacon_omelet"], "category_multipliers": NORMAL, "signals": [{"category": "burger", "direction": "up", "text": "两万人比赛即将散场，下一轮汉堡需求可能大幅升高。"}, {"category": "burger", "direction": "up", "text": "场外餐车全部停业，下一轮汉堡需求可能进一步升高。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_burger", "classic_burger", "avocado_salad"], "category_multipliers": BURGER_BOOM, "signals": [{"category": "burger", "direction": "up", "text": "体育馆安排第二场满座比赛，下一轮汉堡需求可能保持高位。"}, {"category": "burger", "direction": "up", "text": "新增旅游巴士抵达，下一轮汉堡需求可能继续升高。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["avocado_burger", "classic_burger", "pumpkin_sausage_soup"], "category_multipliers": BURGER_BOOM, "signals": [{"category": "burger", "direction": "up", "text": "决赛观众数量继续增加，下一轮汉堡需求可能保持高位。"}, {"category": "burger", "direction": "up", "text": "周边餐厅提前关门，下一轮汉堡需求可能继续升高。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["avocado_burger", "classic_burger", "corn_bacon_omelet"], "category_multipliers": BURGER_BOOM, "signals": [{"category": "sandwich", "direction": "up", "text": "铁路大面积晚点，下一轮三明治需求可能升高。"}, {"category": "sandwich", "direction": "up", "text": "商务会议追加便携盒餐，下一轮三明治需求可能升高。"}], "baseline_recipe_id": "classic_burger"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "garden_fish_sandwich", "garden_salad"], "category_multipliers": SANDWICH_BOOM, "signals": [{"category": "sandwich", "direction": "up", "text": "铁路延误持续，下一轮三明治需求可能保持高位。"}, {"category": "sandwich", "direction": "up", "text": "车站食品区关闭，下一轮三明治需求可能继续升高。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "garden_fish_sandwich", "broccoli_bacon_omelet"], "category_multipliers": SANDWICH_BOOM, "signals": [{"category": "sandwich", "direction": "up", "text": "商务会议延长，下一轮三明治需求可能保持高位。"}, {"category": "sandwich", "direction": "up", "text": "旅游巴士新增乘客，下一轮三明治需求可能继续升高。"}], "baseline_recipe_id": "garden_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "garden_fish_sandwich", "pumpkin_sausage_soup"], "category_multipliers": SANDWICH_BOOM, "signals": [{"category": "salad", "direction": "up", "text": "大型健康展开放，下一轮沙拉需求可能升高。"}, {"category": "salad", "direction": "up", "text": "高温天气增加轻食需求，下一轮沙拉需求可能进一步升高。"}], "baseline_recipe_id": "garden_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_salad", "garden_salad", "corn_bacon_omelet"], "category_multipliers": SALAD_BOOM, "signals": [{"category": "omelet", "direction": "up", "text": "工厂增加大规模早班，下一轮煎蛋卷需求可能升高。"}, {"category": "omelet", "direction": "up", "text": "车站早餐摊关闭，下一轮煎蛋卷需求可能进一步升高。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "broccoli_bacon_omelet", "garden_salad"], "category_multipliers": OMELET_BOOM, "signals": [], "baseline_recipe_id": "corn_bacon_omelet"},
		]
	},
	{
		"id": "E", "strategy": "one_round_lookahead", "rounds": [
			{"candidate_recipe_ids": ["avocado_burger", "avocado_salad", "carrot_sausage_soup"], "category_multipliers": NORMAL, "signals": [{"category": "salad", "direction": "up", "text": "健康市集进入午餐时段，下一轮沙拉需求可能升高。"}, {"category": "salad", "direction": "up", "text": "天气炎热，下一轮轻食需求可能升高。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["avocado_salad", "avocado_burger", "pumpkin_sausage_soup"], "category_multipliers": SALAD_HIGH, "signals": [{"category": "salad", "direction": "up", "text": "健康市集客流翻倍，下一轮沙拉需求可能继续升高。"}, {"category": "salad", "direction": "up", "text": "健身中心餐厅停业，下一轮沙拉需求可能进一步升高。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["avocado_salad", "pumpkin_sausage_soup", "avocado_burger"], "category_multipliers": SALAD_BOOM, "signals": [{"category": "soup", "direction": "up", "text": "夜间气温明显下降，下一轮汤类需求可能升高。"}, {"category": "soup", "direction": "up", "text": "办公区增加夜班，下一轮热汤需求可能升高。"}], "baseline_recipe_id": "avocado_salad"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "avocado_burger", "corn_bacon_omelet"], "category_multipliers": SOUP_HIGH, "signals": [{"category": "soup", "direction": "up", "text": "暴风雨即将抵达，下一轮汤类需求可能继续升高。"}, {"category": "soup", "direction": "up", "text": "附近建筑供暖故障，下一轮汤类需求可能进一步升高。"}], "baseline_recipe_id": "pumpkin_sausage_soup"},
			{"candidate_recipe_ids": ["pumpkin_sausage_soup", "avocado_fish_sandwich", "corn_bacon_omelet"], "category_multipliers": SOUP_BOOM, "signals": [{"category": "burger", "direction": "up", "text": "杯赛半决赛即将散场，下一轮汉堡需求可能升高。"}, {"category": "burger", "direction": "up", "text": "场外餐车供应不足，下一轮汉堡需求可能升高。"}], "baseline_recipe_id": "pumpkin_sausage_soup"},
			{"candidate_recipe_ids": ["avocado_burger", "avocado_fish_sandwich", "corn_bacon_omelet"], "category_multipliers": BURGER_HIGH, "signals": [{"category": "burger", "direction": "up", "text": "冠军赛满座，下一轮汉堡需求可能大幅升高。"}, {"category": "burger", "direction": "up", "text": "周边餐厅提前关闭，下一轮汉堡需求可能进一步升高。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["avocado_burger", "avocado_fish_sandwich", "corn_bacon_omelet"], "category_multipliers": BURGER_BOOM, "signals": [{"category": "sandwich", "direction": "up", "text": "铁路晚点，下一轮三明治需求可能升高。"}, {"category": "sandwich", "direction": "up", "text": "商务会议追加盒餐，下一轮三明治需求可能升高。"}], "baseline_recipe_id": "avocado_burger"},
			{"candidate_recipe_ids": ["garden_fish_sandwich", "corn_bacon_omelet", "broccoli_bacon_omelet"], "category_multipliers": SANDWICH_HIGH, "signals": [{"category": "sandwich", "direction": "up", "text": "铁路故障范围扩大，下一轮三明治需求可能继续升高。"}, {"category": "sandwich", "direction": "up", "text": "会议延长至晚间，下一轮三明治需求可能进一步升高。"}], "baseline_recipe_id": "corn_bacon_omelet"},
			{"candidate_recipe_ids": ["avocado_fish_sandwich", "garden_fish_sandwich", "broccoli_bacon_omelet"], "category_multipliers": SANDWICH_BOOM, "signals": [{"category": "omelet", "direction": "up", "text": "工厂提前开启大规模早班，下一轮煎蛋卷需求可能升高。"}, {"category": "omelet", "direction": "up", "text": "车站早餐区临时关闭，下一轮煎蛋卷需求可能升高。"}], "baseline_recipe_id": "avocado_fish_sandwich"},
			{"candidate_recipe_ids": ["corn_bacon_omelet", "broccoli_bacon_omelet", "garden_salad"], "category_multipliers": OMELET_BOOM, "signals": [], "baseline_recipe_id": "corn_bacon_omelet"},
		]
	},
]


static func campaign_by_id(campaign_id: String) -> Dictionary:
	for campaign: Dictionary in CAMPAIGNS:
		if String(campaign["id"]) == campaign_id:
			return campaign.duplicate(true)
	return {}


static func campaign_for_draw(seed_value: int, draw_index: int) -> Dictionary:
	var indices: Array[int] = [0, 1, 2, 3, 4]
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	for index: int in range(indices.size() - 1, 0, -1):
		var swap_index := random.randi_range(0, index)
		var temporary := indices[index]
		indices[index] = indices[swap_index]
		indices[swap_index] = temporary
	return CAMPAIGNS[indices[posmod(draw_index, indices.size())]].duplicate(true)


static func baseline_profit(campaign: Dictionary) -> int:
	var total := 0
	for round_data: Dictionary in campaign.get("rounds", []):
		var recipe_id := String(round_data.get("baseline_recipe_id", ""))
		var recipe: Dictionary = CATALOG.recipe_by_id(recipe_id)
		if recipe.is_empty():
			return -1
		var multipliers: Dictionary = round_data.get("category_multipliers", {})
		var multiplier := float(multipliers.get(String(recipe["category"]), -1.0))
		var profit := ECONOMY.adjusted_profit(recipe_id, multiplier)
		if profit < 0:
			return -1
		total += profit
	return total


static func passing_profit(campaign: Dictionary) -> int:
	return ceili(float(baseline_profit(campaign)) * TARGET_RATIO)
