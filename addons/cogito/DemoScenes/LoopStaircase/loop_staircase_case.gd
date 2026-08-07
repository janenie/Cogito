class_name LoopStaircaseCase
extends RefCounted

const FLOOR_MIN: int = 2
const FLOOR_MAX: int = 9
const ROUND_COUNT: int = 5
const VICTIM_NAMES: Array[String] = ["林默", "周岚", "沈川", "顾遥", "唐宁", "叶澄"]
const VISITOR_NAMES: Array[String] = ["程野", "许安", "陆青", "苏禾", "闻舟", "江临"]
const TRACKED_ITEMS: Array[String] = ["马克杯", "书本", "台灯", "电脑", "纸箱"]
const SIGNAL_COLORS: Array[String] = ["red", "blue", "green", "white", "yellow", "purple"]
const ROOM_TYPES: Dictionary = {
	2: "lounge",
	3: "lounge",
	4: "archive",
	5: "archive",
	6: "office",
	7: "office",
	8: "meeting",
	9: "meeting",
}
const THEME_IDS: Dictionary = {
	2: "lounge_window",
	3: "lounge_reading",
	4: "archive_paper",
	5: "archive_digital",
	6: "office_manager",
	7: "office_open",
	8: "meeting_round",
	9: "meeting_boardroom",
}

var true_floor: int = FLOOR_MIN
var victim_name: String = ""
var tracked_item: String = ""
var clues: Array[String] = []
var floor_states: Dictionary = {}
var candidate_sets: Array[Array] = []

var _rng := RandomNumberGenerator.new()


static func generate(seed_value: int) -> RefCounted:
	var script := load(
		"res://addons/cogito/DemoScenes/LoopStaircase/loop_staircase_case.gd"
	) as Script
	var result: RefCounted = script.new()
	result._generate(seed_value)
	assert(result.is_consistent(), "generated staircase case is inconsistent")
	return result


func visible_state(floor_number: int, round_index: int) -> Dictionary:
	if not floor_states.has(floor_number):
		return {}
	var data: Dictionary = floor_states[floor_number]
	var index: int = clampi(round_index, 0, ROUND_COUNT - 1)
	return {
		"floor": floor_number,
		"room_type": data["room_type"],
		"theme_id": data["theme_id"],
		"visitor_names": data["visitor_names"].duplicate(),
		"visitor_round_visible": index == ROUND_COUNT - 1,
		"visitor_round": data["visitor_round"],
		"tracked_item": data["tracked_item"],
		"item_count": data["item_counts"][index],
		"trash_count": data["trash_counts"][index],
		"signal_color": data["signal_colors"][index],
		"paired_floor": data["paired_floor"],
	}


func visible_clues(round_index: int) -> Array[String]:
	var result: Array[String] = []
	for index: int in range(clampi(round_index, 0, ROUND_COUNT - 1) + 1):
		result.append(clues[index])
	return result


func test_snapshot() -> Dictionary:
	return {
		"true_floor": true_floor,
		"victim_name": victim_name,
		"tracked_item": tracked_item,
		"clues": clues.duplicate(),
		"floors": floor_states.duplicate(true),
		"candidate_sets": candidate_sets.duplicate(true),
	}


func matching_floors_without(excluded_kind: String) -> Array[int]:
	var result: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		var evidence: Dictionary = _evidence_matches(floor_number)
		var matches: bool = true
		for kind: String in ["visitor", "item", "trash", "signal"]:
			if kind == excluded_kind:
				continue
			if not evidence.get(kind, false):
				matches = false
				break
		if matches:
			result.append(floor_number)
	result.sort()
	return result


func _evidence_matches(floor_number: int) -> Dictionary:
	var data: Dictionary = floor_states[floor_number]
	var item_counts: Array = data["item_counts"]
	var paired_counts: Array = floor_states[data["paired_floor"]]["item_counts"]
	var trash_counts: Array = data["trash_counts"]
	var signal_colors: Array = data["signal_colors"]
	var item_delta: int = item_counts[1] - item_counts[0]
	var paired_delta: int = paired_counts[1] - paired_counts[0]
	return {
		"visitor": victim_name in data["visitor_names"] and data["visitor_round"] == 1,
		"item": item_delta != 0 and paired_delta == -item_delta,
		"trash": trash_counts[1] == trash_counts[0] - 1 and trash_counts[1] == 2,
		"signal": (
			signal_colors[0] == signal_colors[2]
			and signal_colors[1] == signal_colors[3]
			and signal_colors[0] != signal_colors[1]
		),
	}


func is_consistent() -> bool:
	if clues.size() != ROUND_COUNT or floor_states.size() != FLOOR_MAX - FLOOR_MIN + 1:
		return false
	if candidate_sets.size() != 6:
		return false
	var recomputed: Array[Array] = []
	recomputed.append(_all_floors())
	var round_one: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		if victim_name in floor_states[floor_number]["visitor_names"]:
			round_one.append(floor_number)
	recomputed.append(round_one)
	var round_two: Array[int] = []
	for floor_number: int in round_one:
		var item_counts: Array = floor_states[floor_number]["item_counts"]
		if item_counts[1] != item_counts[0]:
			round_two.append(floor_number)
	recomputed.append(round_two)
	var round_three: Array[int] = []
	for floor_number: int in round_two:
		var trash_counts: Array = floor_states[floor_number]["trash_counts"]
		if trash_counts[1] == trash_counts[0] - 1 and trash_counts[2] == trash_counts[1] - 1:
			round_three.append(floor_number)
	recomputed.append(round_three)
	var round_four: Array[int] = []
	for floor_number: int in round_three:
		var colors: Array = floor_states[floor_number]["signal_colors"]
		if colors[0] == colors[2] and colors[1] == colors[3] and colors[0] != colors[1]:
			round_four.append(floor_number)
	recomputed.append(round_four)
	recomputed.append(matching_floors_without(""))
	for index: int in range(recomputed.size()):
		if recomputed[index] != candidate_sets[index]:
			return false
	for kind: String in ["visitor", "item", "trash", "signal"]:
		if matching_floors_without(kind).size() <= 1:
			return false
	return candidate_sets.map(func(values: Array) -> int: return values.size()) == [8, 6, 5, 3, 2, 1]


func _generate(seed_value: int) -> void:
	_rng = RandomNumberGenerator.new()
	if seed_value == 0:
		_rng.randomize()
	else:
		_rng.seed = seed_value
	var shuffled: Array[int] = _all_floors()
	_shuffle_ints(shuffled)
	true_floor = shuffled[0]
	var visitor_miss: int = _paired_floor(true_floor)
	var pair_starts: Array[int] = [2, 4, 6, 8]
	pair_starts.erase(mini(true_floor, visitor_miss))
	_shuffle_ints(pair_starts)
	var second_pair_start: int = pair_starts[0]
	var signal_miss: int = second_pair_start + _rng.randi_range(0, 1)
	var trash_miss: int = _paired_floor(signal_miss)
	var remaining: Array[int] = _all_floors()
	for selected_floor: int in [true_floor, visitor_miss, signal_miss, trash_miss]:
		remaining.erase(selected_floor)
	_shuffle_ints(remaining)
	var zero_trash: int = remaining[0]
	var item_miss: int = remaining[1]
	var round_four: Array[int] = _sorted([true_floor, visitor_miss])
	var round_three: Array[int] = _sorted(round_four + [signal_miss])
	var round_two: Array[int] = _sorted(round_three + [zero_trash, trash_miss])
	var round_one: Array[int] = _sorted(round_two + [item_miss])
	candidate_sets = [_all_floors(), round_one, round_two, round_three, round_four, [true_floor]]
	victim_name = VICTIM_NAMES[_rng.randi_range(0, VICTIM_NAMES.size() - 1)]
	tracked_item = TRACKED_ITEMS[_rng.randi_range(0, TRACKED_ITEMS.size() - 1)]
	_generate_floor_states(visitor_miss, signal_miss, zero_trash, trash_miss, item_miss)
	clues = [
		"寻找访客记录中出现“%s”的房间。" % victim_name,
		"比较前两轮，寻找“%s”数量发生普通变化的房间。" % tracked_item,
		"清洁员每次经过房间，只会顺手带走一件垃圾。",
		"秘密相关的状态灯只使用两种颜色，并保持一明一暗式交替。",
		"受害者的关键访问发生在第二轮：同功能配对房间的物品转移、第一次顺手清理与双色交替的第二相位必须同时成立。",
	]


func _generate_floor_states(
	visitor_miss: int,
	signal_miss: int,
	zero_trash: int,
	trash_miss: int,
	item_miss: int,
) -> void:
	floor_states.clear()
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		var visitors: Array[String] = [VISITOR_NAMES[(floor_number - FLOOR_MIN) % VISITOR_NAMES.size()]]
		if floor_number in candidate_sets[1]:
			visitors.append(victim_name)
		var item_base: int = 1 + ((floor_number + _rng.randi_range(0, 2)) % 3)
		var item_counts: Array[int] = [item_base, item_base, item_base, item_base, item_base]
		if floor_number in [true_floor, signal_miss, zero_trash]:
			item_counts = [item_base, item_base + 1, item_base + 1, item_base + 1, item_base + 1]
		elif floor_number in [visitor_miss, trash_miss]:
			item_counts = [item_base, item_base - 1, item_base - 1, item_base - 1, item_base - 1]
		var trash_counts: Array[int] = [2, 2, 2, 1, 1]
		if floor_number in [true_floor, visitor_miss, signal_miss, item_miss]:
			trash_counts = [3, 2, 1, 0, 0]
		elif floor_number in candidate_sets[3]:
			trash_counts = [4, 3, 2, 1, 0]
		elif floor_number == zero_trash:
			trash_counts = [0, 0, 0, 0, 0]
		elif floor_number == trash_miss:
			trash_counts = [4, 2, 1, 1, 0]
		var signal_colors: Array[String] = ["red", "green", "green", "red", "white"]
		if floor_number == true_floor:
			signal_colors = ["red", "blue", "red", "blue", "red"]
		elif floor_number == visitor_miss:
			signal_colors = ["yellow", "blue", "yellow", "blue", "yellow"]
		elif floor_number == signal_miss:
			signal_colors = ["blue", "red", "red", "blue", "white"]
		elif floor_number == item_miss:
			signal_colors = ["green", "blue", "green", "blue", "green"]
		elif floor_number == trash_miss:
			signal_colors = ["red", "blue", "red", "blue", "white"]
		floor_states[floor_number] = {
			"floor": floor_number,
			"room_type": ROOM_TYPES[floor_number],
			"theme_id": THEME_IDS[floor_number],
			"paired_floor": floor_number + 1 if floor_number % 2 == 0 else floor_number - 1,
			"visitor_names": visitors,
			"visitor_round": 2 if floor_number == visitor_miss else 1,
			"tracked_item": tracked_item,
			"item_counts": item_counts,
			"trash_counts": trash_counts,
			"signal_colors": signal_colors,
			"transfer_round": 1,
			"final_phase": signal_colors[1],
		}


func _all_floors() -> Array[int]:
	var result: Array[int] = []
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		result.append(floor_number)
	return result


func _paired_floor(floor_number: int) -> int:
	return floor_number + 1 if floor_number % 2 == 0 else floor_number - 1


func _sorted(values: Array) -> Array[int]:
	var result: Array[int] = []
	for value: Variant in values:
		result.append(int(value))
	result.sort()
	return result


func _shuffle_ints(values: Array[int]) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index: int = _rng.randi_range(0, index)
		var value: int = values[index]
		values[index] = values[swap_index]
		values[swap_index] = value
