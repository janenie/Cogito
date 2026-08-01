extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	_test_seeded_generation()
	_test_control_and_breaker_behavior()
	_test_snapshot_is_isolated()
	_finish()


func _test_seeded_generation() -> void:
	var first := AIPlayLightingCircuitRound.new()
	var second := AIPlayLightingCircuitRound.new()
	first.configure(87123)
	second.configure(87123)
	_assert(first.snapshot() == second.snapshot(), "same seed is deterministic")

	for seed_value: int in range(1, 257):
		var round_state := AIPlayLightingCircuitRound.new()
		round_state.configure(seed_value)
		var state: Dictionary = round_state.snapshot()
		var mapped: Array = state.mapping.values()
		mapped.sort()
		_assert(
			mapped == ["break_room", "ceo", "entrance", "lobby"],
			"mapping is a permutation for seed %d" % seed_value,
		)
		_assert(
			_difference_count(state.initial_states, state.target_states) >= 2,
			"target differs twice for seed %d" % seed_value,
		)
		_assert(
			state.target_states[state.fault_circuit] == true,
			"fault target is on for seed %d" % seed_value,
		)


func _test_control_and_breaker_behavior() -> void:
	var round_state := AIPlayLightingCircuitRound.new()
	round_state.configure(9012)
	var state: Dictionary = round_state.snapshot()
	var fault_circuit: String = state.fault_circuit
	var fault_control: String = round_state.control_for_circuit(fault_circuit)
	var normal_circuit: String = ""
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		if circuit_id != fault_circuit:
			normal_circuit = circuit_id
			break
	var normal_control: String = round_state.control_for_circuit(normal_circuit)
	var fault_before: bool = state.circuit_states[fault_circuit]
	var fault_result := round_state.set_control_state(
		fault_control,
		not state.control_states[fault_control],
	)
	_assert(
		fault_result.accepted and not fault_result.applied,
		"fault indicator changes without lamp",
	)
	_assert(
		round_state.snapshot().circuit_states[fault_circuit] == fault_before,
		"fault lamp stays unchanged",
	)

	var normal_result := round_state.set_control_state(
		normal_control,
		not state.control_states[normal_control],
	)
	_assert(
		normal_result.accepted and normal_result.applied,
		"normal circuit applies",
	)
	_assert(
		round_state.snapshot().circuit_states[normal_result.circuit]
			== normal_result.state,
		"normal lamp follows",
	)
	_assert(
		round_state.set_control_state("unknown", true) == {"accepted": false},
		"unknown control is rejected",
	)

	var wrong := round_state.reset_breaker(normal_result.circuit)
	_assert(wrong.accepted and not wrong.correct, "wrong breaker consumes the attempt")
	_assert(
		not round_state.reset_breaker(fault_circuit).accepted,
		"second breaker is rejected",
	)

	round_state.configure(87123)
	_assert(
		round_state.reset_breaker("unknown") == {"accepted": false},
		"unknown breaker does not consume the attempt",
	)
	var correct := round_state.reset_breaker(round_state.snapshot().fault_circuit)
	_assert(correct.accepted and correct.correct, "correct breaker restores the circuit")
	_assert(
		round_state.snapshot().circuit_states[correct.circuit] == correct.state,
		"repair syncs current control",
	)
	_assert(
		not round_state.reset_breaker(correct.circuit).accepted,
		"repeated correct breaker is rejected",
	)
	_set_controls_to_targets(round_state)
	_assert(
		round_state.is_configuration_correct(),
		"repaired target configuration is correct",
	)

	var incorrect_control: String = AIPlayLightingCircuitRound.CONTROL_IDS[0]
	var incorrect_state: Dictionary = round_state.snapshot()
	round_state.set_control_state(
		incorrect_control,
		not incorrect_state.control_states[incorrect_control],
	)
	_assert(
		not round_state.is_configuration_correct(),
		"post-repair wrong state is rejected",
	)


func _test_snapshot_is_isolated() -> void:
	var round_state := AIPlayLightingCircuitRound.new()
	round_state.configure(42)
	var snapshot: Dictionary = round_state.snapshot()
	snapshot.mapping["A"] = "mutated"
	snapshot.initial_states["entrance"] = not snapshot.initial_states["entrance"]
	var fresh: Dictionary = round_state.snapshot()
	_assert(fresh.mapping["A"] != "mutated", "snapshot mapping is duplicated")
	_assert(
		fresh.initial_states["entrance"] != snapshot.initial_states["entrance"],
		"snapshot state is duplicated",
	)


func _difference_count(left: Dictionary, right: Dictionary) -> int:
	var count: int = 0
	for circuit_id: String in AIPlayLightingCircuitRound.CIRCUIT_IDS:
		if left[circuit_id] != right[circuit_id]:
			count += 1
	return count


func _set_controls_to_targets(round_state: AIPlayLightingCircuitRound) -> void:
	var state: Dictionary = round_state.snapshot()
	for control_id: String in AIPlayLightingCircuitRound.CONTROL_IDS:
		var circuit_id: String = state.mapping[control_id]
		round_state.set_control_state(control_id, state.target_states[circuit_id])


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay lighting circuit round tests passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
