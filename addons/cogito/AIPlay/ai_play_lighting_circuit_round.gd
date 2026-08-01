class_name AIPlayLightingCircuitRound
extends RefCounted

const CONTROL_IDS: Array[String] = ["A", "B", "C", "D"]
const CIRCUIT_IDS: Array[String] = ["entrance", "ceo", "lobby", "break_room"]

var mapping: Dictionary = {}
var fault_circuit: String = ""
var initial_states: Dictionary = {}
var target_states: Dictionary = {}
var control_states: Dictionary = {}
var circuit_states: Dictionary = {}
var breaker_attempted: bool = false
var breaker_restored: bool = false


func configure(seed_value: int) -> void:
	mapping.clear()
	fault_circuit = ""
	initial_states.clear()
	target_states.clear()
	control_states.clear()
	circuit_states.clear()
	breaker_attempted = false
	breaker_restored = false

	var rng := RandomNumberGenerator.new()
	if seed_value == 0:
		rng.randomize()
	else:
		rng.seed = seed_value

	var shuffled_circuits: Array[String] = CIRCUIT_IDS.duplicate()
	_shuffle_with_rng(shuffled_circuits, rng)
	for index: int in range(CONTROL_IDS.size()):
		mapping[CONTROL_IDS[index]] = shuffled_circuits[index]

	fault_circuit = CIRCUIT_IDS[rng.randi_range(0, CIRCUIT_IDS.size() - 1)]
	for circuit_id: String in CIRCUIT_IDS:
		initial_states[circuit_id] = rng.randi_range(0, 1) == 1
		target_states[circuit_id] = rng.randi_range(0, 1) == 1
	target_states[fault_circuit] = true

	var difference_count: int = _difference_count(initial_states, target_states)
	if difference_count < 2:
		var non_fault_circuits: Array[String] = []
		for circuit_id: String in CIRCUIT_IDS:
			if circuit_id != fault_circuit:
				non_fault_circuits.append(circuit_id)
		_shuffle_with_rng(non_fault_circuits, rng)
		for circuit_id: String in non_fault_circuits:
			if difference_count >= 2:
				break
			if target_states[circuit_id] == initial_states[circuit_id]:
				target_states[circuit_id] = not initial_states[circuit_id]
				difference_count += 1

	for control_id: String in CONTROL_IDS:
		var circuit_id: String = mapping[control_id]
		control_states[control_id] = initial_states[circuit_id]
	circuit_states = initial_states.duplicate(true)


func control_for_circuit(circuit_id: String) -> String:
	for control_id: String in CONTROL_IDS:
		if mapping.get(control_id, "") == circuit_id:
			return control_id
	return ""


func set_control_state(control_id: String, is_on: bool) -> Dictionary:
	if control_id not in mapping:
		return {"accepted": false}
	control_states[control_id] = is_on
	var circuit_id: String = mapping[control_id]
	var applied: bool = circuit_id != fault_circuit or breaker_restored
	if applied:
		circuit_states[circuit_id] = is_on
	return {
		"accepted": true,
		"applied": applied,
		"circuit": circuit_id,
		"state": is_on,
	}


func reset_breaker(circuit_id: String) -> Dictionary:
	if breaker_attempted or circuit_id not in CIRCUIT_IDS:
		return {"accepted": false}
	breaker_attempted = true
	var correct: bool = circuit_id == fault_circuit
	if not correct:
		return {"accepted": true, "correct": false, "circuit": circuit_id}
	breaker_restored = true
	var control_id: String = control_for_circuit(circuit_id)
	circuit_states[circuit_id] = control_states[control_id]
	return {
		"accepted": true,
		"correct": true,
		"circuit": circuit_id,
		"state": circuit_states[circuit_id],
	}


func is_configuration_correct() -> bool:
	if not breaker_restored:
		return false
	for circuit_id: String in CIRCUIT_IDS:
		if circuit_states[circuit_id] != target_states[circuit_id]:
			return false
	return true


func snapshot() -> Dictionary:
	return {
		"mapping": mapping.duplicate(true),
		"fault_circuit": fault_circuit,
		"initial_states": initial_states.duplicate(true),
		"target_states": target_states.duplicate(true),
		"control_states": control_states.duplicate(true),
		"circuit_states": circuit_states.duplicate(true),
		"breaker_attempted": breaker_attempted,
		"breaker_restored": breaker_restored,
	}


func _shuffle_with_rng(
	values: Array[String],
	rng: RandomNumberGenerator,
) -> void:
	for index: int in range(values.size() - 1, 0, -1):
		var swap_index: int = rng.randi_range(0, index)
		var temporary: String = values[index]
		values[index] = values[swap_index]
		values[swap_index] = temporary


func _difference_count(left: Dictionary, right: Dictionary) -> int:
	var count: int = 0
	for circuit_id: String in CIRCUIT_IDS:
		if left[circuit_id] != right[circuit_id]:
			count += 1
	return count
