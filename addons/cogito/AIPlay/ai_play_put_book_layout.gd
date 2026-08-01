class_name AIPlayPutBookLayout
extends RefCounted

const HEIGHT_TIERS: Array[String] = ["low", "middle", "high"]
const BOOKS_PER_TIER := 2


static func slot_id(slot: Marker3D) -> String:
	return String(slot.get_meta("slot_id", ""))


static func shelf_id(slot: Marker3D) -> String:
	return String(slot.get_meta("shelf_id", ""))


static func height_tier(slot: Marker3D) -> String:
	return String(slot.get_meta("height_tier", ""))


static func select_slots(
	slots: Array[Marker3D],
	rng: RandomNumberGenerator,
) -> Array[Marker3D]:
	var by_tier: Dictionary = {}
	for tier: String in HEIGHT_TIERS:
		by_tier[tier] = []
	var seen_ids: Dictionary = {}
	for slot: Marker3D in slots:
		var id := slot_id(slot)
		var shelf := shelf_id(slot)
		var tier := height_tier(slot)
		if id.is_empty() or shelf.is_empty() or tier not in HEIGHT_TIERS:
			continue
		if seen_ids.has(id):
			continue
		seen_ids[id] = true
		(by_tier[tier] as Array).append(slot)

	var tier_pairs: Dictionary = {}
	for tier: String in HEIGHT_TIERS:
		tier_pairs[tier] = _pairs(by_tier[tier] as Array)
		if (tier_pairs[tier] as Array).is_empty():
			return []

	var best_layouts: Array[Array] = []
	var best_score: Array[int] = []
	for low_pair: Array in tier_pairs["low"]:
		for middle_pair: Array in tier_pairs["middle"]:
			for high_pair: Array in tier_pairs["high"]:
				var layout: Array = low_pair + middle_pair + high_pair
				var score := _shelf_score(layout)
				if best_score.is_empty() or _score_less(score, best_score):
					best_score = score
					best_layouts = [layout]
				elif score == best_score:
					best_layouts.append(layout)
	if best_layouts.is_empty():
		return []
	var chosen: Array = best_layouts[rng.randi_range(0, best_layouts.size() - 1)]
	var result: Array[Marker3D] = []
	for value: Variant in chosen:
		result.append(value as Marker3D)
	return result


static func _pairs(values: Array) -> Array[Array]:
	var result: Array[Array] = []
	for first: int in range(values.size()):
		for second: int in range(first + 1, values.size()):
			result.append([values[first], values[second]])
	return result


static func _shelf_score(layout: Array) -> Array[int]:
	var counts: Dictionary = {}
	for value: Variant in layout:
		var shelf := shelf_id(value as Marker3D)
		counts[shelf] = int(counts.get(shelf, 0)) + 1
	var score: Array[int] = []
	for count: Variant in counts.values():
		score.append(int(count))
	score.sort()
	score.reverse()
	while score.size() < 3:
		score.append(0)
	return score


static func _score_less(left: Array[int], right: Array[int]) -> bool:
	for index: int in range(mini(left.size(), right.size())):
		if left[index] != right[index]:
			return left[index] < right[index]
	return left.size() < right.size()
