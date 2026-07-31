class_name LaboratoryExperimentCases
extends RefCounted

const BATTERY_LABELS: Array[String] = ["alpha", "beta", "gamma"]
const BATTERY_PROFILES: Array[String] = ["low", "nominal", "high"]
const SAMPLE_LABELS: Array[String] = ["a", "b", "c"]
const SAMPLE_POOL: Array[String] = [
	"wet_conductor",
	"dry_conductor",
	"heat_activated",
	"heat_sensitive",
	"high_resistance",
	"insulator",
]

static var CASES: Array[Dictionary] = [
	_case("stable_conduction", "standard", "nominal", "dry_conductor", "dry", 0),
	_case("stable_conduction", "standard", "high", "high_resistance", "dry", 1),
	_case("stable_conduction", "standard", "nominal", "wet_conductor", "wet", 2),
	_case("stable_conduction", "power_fluctuation", "nominal", "heat_activated", "heated", 3),
	_case("moisture_safety", "standard", "nominal", "wet_conductor", "wet", 4),
	_case("moisture_safety", "high_humidity", "low", "wet_conductor", "wet", 5),
	_case("moisture_safety", "standard", "high", "high_resistance", "wet", 6),
	_case("moisture_safety", "power_fluctuation", "nominal", "wet_conductor", "wet", 7),
	_case("thermal_tolerance", "standard", "nominal", "heat_activated", "heated", 8),
	_case("thermal_tolerance", "high_humidity", "nominal", "heat_activated", "heated", 9),
	_case("thermal_tolerance", "standard", "high", "high_resistance", "heated", 10),
	_case("thermal_tolerance", "power_fluctuation", "nominal", "heat_activated", "heated", 11),
]


static func _case(
	protocol: String,
	environment: String,
	battery_profile: String,
	sample_profile: String,
	treatment: String,
	clue_variant: int,
) -> Dictionary:
	return {
		"protocol": protocol,
		"environment": environment,
		"correct_battery_profile": battery_profile,
		"correct_sample_profile": sample_profile,
		"correct_treatment": treatment,
		"clue_variant": clue_variant,
	}


static func build_round(seed: int) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = seed
	var case_index := rng.randi_range(0, CASES.size() - 1)
	var case: Dictionary = CASES[case_index]
	var sample_profiles: Array[String] = _sample_profiles_for_case(
		case["correct_sample_profile"],
		rng,
	)
	var round_data := {
		"case_id": case_index,
		"protocol": case["protocol"],
		"environment": case["environment"],
		"battery_map": _shuffled_map(rng, BATTERY_LABELS, BATTERY_PROFILES),
		"sample_map": _shuffled_map(rng, SAMPLE_LABELS, sample_profiles),
		"correct_battery_profile": case["correct_battery_profile"],
		"correct_sample_profile": case["correct_sample_profile"],
		"correct_treatment": case["correct_treatment"],
		"clues": _clues_for_case(case),
	}
	_assert_unique_solution(round_data)
	return round_data


static func evaluate(
	round_data: Dictionary,
	battery_label: String,
	sample_label: String,
	treatment: String,
) -> Dictionary:
	var battery_profile: String = round_data.get("battery_map", {}).get(
		battery_label,
		"low",
	)
	var sample_profile: String = round_data.get("sample_map", {}).get(
		sample_label,
		"insulator",
	)
	var result := _material_result(
		battery_profile,
		sample_profile,
		treatment,
		round_data.get("environment", "standard"),
	)
	var exact_match: bool = (
		battery_profile == round_data.get("correct_battery_profile")
		and sample_profile == round_data.get("correct_sample_profile")
		and treatment == round_data.get("correct_treatment")
	)
	result["success"] = exact_match and result["safe"] and result["lamp"] == "stable"
	return result


static func _material_result(
	battery: String,
	sample: String,
	treatment: String,
	environment: String,
) -> Dictionary:
	var conductivity := "zero"
	var stability := "interrupted"
	var temperature := "safe"

	match sample:
		"wet_conductor":
			if treatment == "wet":
				conductivity = _battery_current(battery)
				stability = "stable"
		"dry_conductor":
			if treatment == "dry":
				conductivity = _battery_current(battery)
				stability = "stable"
			elif treatment == "wet":
				conductivity = "high"
				stability = "interrupted"
			else:
				conductivity = "low"
				stability = "flicker"
				temperature = "elevated"
		"heat_activated":
			if treatment == "heated":
				conductivity = _battery_current(battery)
				stability = "stable"
				temperature = "elevated"
			elif treatment == "wet":
				conductivity = "low"
				stability = "flicker"
		"heat_sensitive":
			if treatment == "dry":
				conductivity = _battery_current(battery)
				stability = "stable"
			elif treatment == "wet":
				conductivity = "low"
				stability = "flicker"
			else:
				conductivity = "high"
				stability = "interrupted"
				temperature = "dangerous"
		"high_resistance":
			conductivity = "safe" if battery == "high" else "low"
			stability = "stable" if battery == "high" else "flicker"
			if treatment == "heated":
				temperature = "elevated"
		"insulator":
			pass

	if treatment == "wet" and environment == "high_humidity":
		conductivity = _raise_current(conductivity)
	if treatment == "heated" and environment == "limited_cooling":
		temperature = _raise_temperature(temperature)
	if battery == "high" and environment == "power_fluctuation" and stability == "stable":
		stability = "flicker"

	var safe := (
		conductivity not in ["zero", "high"]
		and stability == "stable"
		and temperature != "dangerous"
	)
	return {
		"power": {"low": "low", "nominal": "normal", "high": "high"}[battery],
		"current": conductivity,
		"stability": stability,
		"temperature": temperature,
		"lamp": _lamp_result(conductivity, stability),
		"safe": safe,
		"success": false,
	}


static func _battery_current(battery: String) -> String:
	return {"low": "low", "nominal": "safe", "high": "high"}[battery]


static func _raise_current(current: String) -> String:
	return {"zero": "low", "low": "safe", "safe": "high", "high": "high"}[current]


static func _raise_temperature(temperature: String) -> String:
	return {
		"safe": "elevated",
		"elevated": "dangerous",
		"dangerous": "dangerous",
	}[temperature]


static func _lamp_result(current: String, stability: String) -> String:
	if current == "zero" or stability == "interrupted":
		return "off"
	if stability == "flicker":
		return "flicker"
	if current == "low":
		return "dim"
	return "stable" if current == "safe" else "flicker"


static func _sample_profiles_for_case(
	correct_profile: String,
	rng: RandomNumberGenerator,
) -> Array[String]:
	var candidates := SAMPLE_POOL.duplicate()
	candidates.erase(correct_profile)
	_shuffle(rng, candidates)
	return [correct_profile, candidates[0], candidates[1]]


static func _shuffled_map(
	rng: RandomNumberGenerator,
	labels: Array[String],
	values: Array[String],
) -> Dictionary:
	var shuffled := values.duplicate()
	_shuffle(rng, shuffled)
	var result := {}
	for index: int in labels.size():
		result[labels[index]] = shuffled[index]
	return result


static func _shuffle(rng: RandomNumberGenerator, values: Array[String]) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index := rng.randi_range(0, index)
		var value := values[index]
		values[index] = values[swap_index]
		values[swap_index] = value


static func _clues_for_case(case: Dictionary) -> Array[String]:
	var treatment_clue: String = {
		"dry": "The target sample conducts without treatment.",
		"wet": "The target sample must be wet during the test.",
		"heated": "The target sample activates only after heating.",
	}[case["correct_treatment"]]
	var battery_clue: String = {
		"low": "Use the lowest safe output cell.",
		"nominal": "The required source is neither low nor high output.",
		"high": "The target material needs the strongest available source.",
	}[case["correct_battery_profile"]]
	return [treatment_clue, battery_clue]


static func _assert_unique_solution(round_data: Dictionary) -> void:
	var solution_count := 0
	for battery: String in BATTERY_LABELS:
		for sample: String in SAMPLE_LABELS:
			for treatment: String in ["dry", "wet", "heated"]:
				if evaluate(round_data, battery, sample, treatment)["success"]:
					solution_count += 1
	assert(solution_count == 1, "laboratory experiment case must have one solution")
