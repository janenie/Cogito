extends SceneTree

var _failures: Array[String] = []
var _interaction_script: GDScript
var _player_interaction_script: GDScript


class FakeMonitor extends Node:
	var result: Dictionary = {"accepted": true}
	var calls: Array[Dictionary] = []

	func place_carried_folder(
		seat_id: String,
		player_interaction: Variant,
	) -> Dictionary:
		calls.append({
			"seat_id": seat_id,
			"player_interaction": player_interaction,
		})
		return result.duplicate(true)


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	_interaction_script = load(
		"res://addons/cogito/AIPlay/ai_play_meeting_seat_interaction.gd"
	)
	_player_interaction_script = load(
		"res://addons/cogito/Components/PlayerInteractionComponent.gd"
	)
	_assert(_interaction_script != null, "meeting seat interaction script loads")
	_assert(_player_interaction_script != null, "player interaction script loads")
	if _interaction_script == null or _player_interaction_script == null:
		_finish()
		return
	_test_defaults_and_accepted_delegation()
	_test_neutral_rejection_hints()
	_test_disabled_interaction()
	_finish()


func _test_defaults_and_accepted_delegation() -> void:
	var interaction: Node = _interaction_script.new()
	var monitor := FakeMonitor.new()
	var player_interaction: Node = _player_interaction_script.new()
	interaction.monitor = monitor
	interaction.seat_id = "tv_side"
	var audit_events: Array = []
	interaction.was_interacted_with.connect(
		func(text: String, action: String) -> void:
			audit_events.append([text, action])
	)

	_assert(interaction.input_map_action == "interact2", "seat uses carry action")
	_assert(interaction.interaction_text == "放置资料", "seat has neutral prompt")
	_assert(interaction.prefer_while_carrying, "seat is preferred while carrying")
	interaction.interact(player_interaction)
	_assert(monitor.calls.size() == 1, "accepted request delegates once")
	if monitor.calls.size() == 1:
		_assert(monitor.calls[0].seat_id == "tv_side", "seat ID is preserved")
		_assert(
			monitor.calls[0].player_interaction == player_interaction,
			"player interaction object is preserved",
		)
	_assert(
		audit_events == [["放置资料", "interact2"]],
		"accepted request emits normal audit signal",
	)
	interaction.free()
	player_interaction.free()
	monitor.free()


func _test_neutral_rejection_hints() -> void:
	for rejection: Dictionary in [
		{
			"reason": "occupied",
			"expected": "该席位已有资料",
		},
		{
			"reason": "invalid_folder",
			"expected": "请先拿起会议资料",
		},
		{
			"reason": "not_carrying",
			"expected": "请先拿起会议资料",
		},
	]:
		var interaction: Node = _interaction_script.new()
		var monitor := FakeMonitor.new()
		var player_interaction: Node = _player_interaction_script.new()
		monitor.result = {
			"accepted": false,
			"reason": rejection.reason,
		}
		interaction.monitor = monitor
		interaction.seat_id = "door_side"
		var hints: Array[String] = []
		player_interaction.hint_prompt.connect(
			func(_icon: Texture2D, text: String) -> void: hints.append(text)
		)

		interaction.interact(player_interaction)
		_assert(hints == [rejection.expected], "%s has neutral hint" % rejection.reason)
		for forbidden: String in ["正确", "错误", "答案"]:
			_assert(forbidden not in hints[0], "rejection does not reveal correctness")
		interaction.free()
		player_interaction.free()
		monitor.free()


func _test_disabled_interaction() -> void:
	var interaction: Node = _interaction_script.new()
	var monitor := FakeMonitor.new()
	var player_interaction: Node = _player_interaction_script.new()
	interaction.monitor = monitor
	interaction.seat_id = "inner_wall"
	interaction.is_disabled = true
	interaction.interact(player_interaction)
	_assert(monitor.calls.is_empty(), "disabled interaction does not delegate")
	interaction.free()
	player_interaction.free()
	monitor.free()


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay meeting seat interaction tests passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
