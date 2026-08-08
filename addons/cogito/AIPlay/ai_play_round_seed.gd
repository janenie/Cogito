class_name AIPlayRoundSeed
extends RefCounted

const ARG_PREFIX: String = "--ai-play-round-seed="
const LEGACY_ARG_PREFIX: String = "--ai-play-seed="
const MAX_SAFE_JSON_INTEGER: int = 9_007_199_254_740_991
const DETERMINISTIC_ZERO_RUNTIME_SEED: int = MAX_SAFE_JSON_INTEGER + 1


static func parse(user_args: Array, allow_legacy: bool = false) -> Dictionary:
	var result := {
		"valid": true,
		"provided": false,
		"value": 0,
		"legacy": false,
	}
	var raw_value := ""
	for value: Variant in user_args:
		if not value is String:
			continue
		var argument := value as String
		var is_legacy := false
		var matched := false
		if argument.begins_with(ARG_PREFIX):
			raw_value = argument.trim_prefix(ARG_PREFIX)
			matched = true
		elif allow_legacy and argument.begins_with(LEGACY_ARG_PREFIX):
			raw_value = argument.trim_prefix(LEGACY_ARG_PREFIX)
			matched = true
			is_legacy = true
		if not matched:
			continue
		if result["provided"]:
			result["valid"] = false
			return result
		result["provided"] = true
		result["legacy"] = is_legacy

	if not result["provided"]:
		return result
	if raw_value.is_empty():
		result["valid"] = false
		return result
	for index: int in range(raw_value.length()):
		var character := raw_value.unicode_at(index)
		if character < 48 or character > 57:
			result["valid"] = false
			return result
	var parsed_value := raw_value.to_int()
	if parsed_value < 0 or parsed_value > MAX_SAFE_JSON_INTEGER:
		result["valid"] = false
		return result
	result["value"] = parsed_value
	return result


static func runtime_seed(value: int) -> int:
	if value == 0:
		return DETERMINISTIC_ZERO_RUNTIME_SEED
	return value
