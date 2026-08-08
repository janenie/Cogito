extends SceneTree

const ROUND_SCRIPT_PATH := "res://addons/cogito/AIPlay/ai_play_find_key_round.gd"

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var round_script: GDScript = load(ROUND_SCRIPT_PATH)
	_assert(round_script != null, "find-key round generator exists")
	if round_script == null:
		_finish()
		return

	var expected_packs := {
		"POLARIS": {
			"rooms": ["MEETING_ROOM", "UPPER_OFFICE_CEO", "CUBICLE_AREA"],
			"handlers": ["李明", "王芳", "陈宇"],
		},
		"ATLAS": {
			"rooms": ["UPPER_OFFICE_CEO", "MEETING_ROOM", "CUBICLE_AREA"],
			"handlers": ["陈宇", "李明", "王芳"],
		},
		"ORBIT": {
			"rooms": ["CUBICLE_AREA", "MEETING_ROOM", "UPPER_OFFICE_CEO"],
			"handlers": ["王芳", "陈宇", "李明"],
		},
		"NOVA": {
			"rooms": ["CUBICLE_AREA", "UPPER_OFFICE_CEO", "MEETING_ROOM"],
			"handlers": ["李明", "王芳", "陈宇"],
		},
	}
	var first_cycle: Array[String] = []
	for seed_value: int in range(4):
		var round_data: Dictionary = round_script.build(seed_value)
		var pack_id: String = round_data["pack_id"]
		first_cycle.append(pack_id)
		_assert(round_data["stages"].size() == 3, "three paper stages")
		_assert(round_data["current"]["version"] == "v1.1", "current version is v1.1")
		_assert(round_data["current"]["status"] == "SUBMITTED", "v1.1 is submitted")
		_assert(
			round_data["current"]["minutes_before_noon"] > 0,
			"current submission precedes noon",
		)
		_assert(_unique_count(round_data["all_codes"]) == 4, "codes are unique")
		var stage_bodies: Array[String] = []
		for stage: Dictionary in round_data["stages"]:
			var body: String = stage.get("contract_body", "")
			stage_bodies.append(body)
			for required_section: String in [
				"项目范围 / SCOPE",
				"履约期限 / TERM：生效之日起三个月",
				"合同金额 / VALUE",
				"交付里程碑 / MILESTONES",
				"付款安排 / PAYMENT",
				"本版修订 / REVISION",
			]:
				_assert(
					body.contains(required_section),
					"%s contains substantive section: %s"
					% [stage["version"], required_section],
				)
			for password: String in round_data["all_codes"]:
				_assert(
					not body.contains(password),
					"contract body does not reveal a password",
				)
			if stage["index"] == 2:
				_assert(
					body.contains("签署人 / SIGNATORY：%s" % stage["handler"]),
					"FINAL v1.0 names its signatory",
				)
			else:
				_assert(
					not body.contains("签署人 / SIGNATORY"),
					"non-final draft does not claim a signatory",
				)
		_assert(_unique_count(stage_bodies) == 3, "each version has distinct terms")
		_assert(
			round_data["current"]["password"] == round_data["current"]["time_text"].replace(":", ""),
			"current password is its HHMM submission time",
		)
		var actual_rooms: Array = round_data["stages"].map(
			func(stage: Dictionary) -> String: return stage["room_id"]
		)
		var actual_handlers: Array = round_data["stages"].map(
			func(stage: Dictionary) -> String: return stage["handler"]
		)
		_assert(actual_rooms == expected_packs[pack_id]["rooms"], "%s room matrix" % pack_id)
		_assert(
			actual_handlers == expected_packs[pack_id]["handlers"],
			"%s handler matrix" % pack_id,
		)
		_assert(
			round_data["stages"][0]["timestamp"] < round_data["stages"][1]["timestamp"]
			and round_data["stages"][1]["timestamp"] < round_data["stages"][2]["timestamp"]
			and round_data["stages"][2]["timestamp"] < round_data["current"]["timestamp"],
			"contract events are chronological",
		)

	_assert(_unique_count(first_cycle) == 4, "first cycle has no replacement")
	_assert(round_script.build(2) == round_script.build(2), "same seed reproduces data")
	var exclusive_date_limit := int(
		Time.get_unix_time_from_datetime_dict(
			{
				"year": 2026,
				"month": 8,
				"day": 31,
				"hour": 0,
				"minute": 0,
				"second": 0,
			}
		)
	)
	for boundary_seed: int in [227, 228, 364, 9_007_199_254_740_991]:
		var boundary_round: Dictionary = round_script.build(boundary_seed)
		var dated_records: Array = boundary_round["stages"].duplicate()
		dated_records.append(boundary_round["current"])
		for record: Dictionary in dated_records:
			_assert(
				int(record["timestamp"]) < exclusive_date_limit,
				"seed %d keeps every contract date on or before 2026-08-30"
				% boundary_seed,
			)
	_finish()


func _unique_count(values: Array) -> int:
	var unique := {}
	for value: Variant in values:
		unique[value] = true
	return unique.size()


func _assert(condition: bool, message: String) -> void:
	if condition:
		return
	_failures.append(message)
	push_error(message)


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay find-key round tests passed")
		quit(0)
		return
	print("AIPlay find-key round tests failed: %s" % _failures)
	quit(1)
