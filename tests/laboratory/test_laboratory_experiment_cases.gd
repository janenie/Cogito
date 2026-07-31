extends SceneTree

const Cases = preload(
	"res://addons/cogito/DemoScenes/Laboratory/laboratory_experiment_cases.gd"
)

const BATTERIES: Array[String] = ["alpha", "beta", "gamma"]
const SAMPLES: Array[String] = ["a", "b", "c"]
const TREATMENTS: Array[String] = ["dry", "wet", "heated"]
const RESULT_FIELDS := {
	"power": ["low", "normal", "high"],
	"current": ["zero", "low", "safe", "high"],
	"stability": ["stable", "flicker", "interrupted"],
	"temperature": ["safe", "elevated", "dangerous"],
	"lamp": ["off", "dim", "flicker", "stable"],
}

var failures := 0


func _initialize() -> void:
	var case_library: RefCounted = Cases.new()
	if case_library == null:
		push_error("laboratory experiment case library must compile")
		quit(1)
		return
	_test_all_generated_rounds_have_one_solution()
	_test_same_seed_reproduces_public_round()
	if failures == 0:
		print("Laboratory experiment case tests passed")
		quit(0)
	else:
		push_error("%d laboratory case test(s) failed" % failures)
		quit(1)


func _test_all_generated_rounds_have_one_solution() -> void:
	for seed: int in range(256):
		var round_data: Dictionary = Cases.build_round(seed)
		var successes: Array[Dictionary] = []
		for battery: String in BATTERIES:
			for sample: String in SAMPLES:
				for treatment: String in TREATMENTS:
					var result: Dictionary = Cases.evaluate(
						round_data,
						battery,
						sample,
						treatment,
					)
					_assert_result_is_public_and_bounded(result, seed)
					if result.get("success", false):
						successes.append({
							"battery": battery,
							"sample": sample,
							"treatment": treatment,
						})
		_assert(successes.size() == 1, "seed %d has exactly one solution" % seed)


func _test_same_seed_reproduces_public_round() -> void:
	var first: Dictionary = Cases.build_round(917)
	var second: Dictionary = Cases.build_round(917)
	_assert(first == second, "same seed reproduces the complete round")
	_assert(first.get("clues", []).size() == 2, "round exposes exactly two clues")
	_assert(
		first.get("protocol", "") in [
			"stable_conduction",
			"moisture_safety",
			"thermal_tolerance",
		],
		"round protocol is allowlisted",
	)


func _assert_result_is_public_and_bounded(result: Dictionary, seed: int) -> void:
	var expected_keys := RESULT_FIELDS.keys()
	expected_keys.append_array(["safe", "success"])
	_assert(
		result.keys().all(func(key: Variant) -> bool: return key in expected_keys)
		and result.size() == expected_keys.size(),
		"seed %d result uses exact public fields" % seed,
	)
	for field: String in RESULT_FIELDS:
		_assert(
			result.get(field, "") in RESULT_FIELDS[field],
			"seed %d result %s is bounded" % [seed, field],
		)
	_assert(result.get("safe") is bool, "seed %d safe is boolean" % seed)
	_assert(result.get("success") is bool, "seed %d success is boolean" % seed)


func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
