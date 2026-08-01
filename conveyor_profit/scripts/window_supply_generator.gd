class_name WindowSupplyGenerator
extends RefCounted

const FIXED_DECKS := preload("res://conveyor_profit/scripts/fixed_window_decks.gd")
const PLATE_COUNT: int = 16


static func generate(seed_value: int, window_count: int = 10) -> Array[Dictionary]:
	var random := RandomNumberGenerator.new()
	random.seed = seed_value
	var deck: Dictionary = FIXED_DECKS.deck_for_seed(seed_value)
	var authored_windows: Array = deck.get("windows", [])
	var windows: Array[Dictionary] = []
	for window_index: int in mini(window_count, authored_windows.size()):
		var authored: Dictionary = authored_windows[window_index]
		var ingredients: Array[String] = []
		ingredients.assign(authored.get("ingredients", []))
		_shuffle(ingredients, random)
		windows.append({"ingredients": ingredients})
	return windows


static func _shuffle(values: Array[String], random: RandomNumberGenerator) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index := random.randi_range(0, index)
		var temporary := values[index]
		values[index] = values[swap_index]
		values[swap_index] = temporary
