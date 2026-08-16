extends SceneTree

const AIPlayInteractionProbe = preload("res://addons/cogito/AIPlay/ai_play_interaction_probe.gd")

var _failures: Array[String] = []


class FakePlayer extends Node:
	var MOUSE_SENS: float = 0.25
	var INVERT_Y_AXIS: bool = true
	var is_free_looking: bool = false
	var body: Node3D
	var neck: Node3D
	var head: Node3D
	var camera: Camera3D

	func _init() -> void:
		body = Node3D.new()
		neck = Node3D.new()
		head = Node3D.new()
		camera = Camera3D.new()
		add_child(body)
		body.add_child(neck)
		neck.add_child(head)
		head.add_child(camera)

	func _ready() -> void:
		camera.current = true

	func _input(event: InputEvent) -> void:
		if not event is InputEventMouseMotion:
			return
		var motion := event as InputEventMouseMotion
		if motion.device != AIPlayInteractionProbe.SYNTHETIC_DEVICE_ID:
			return
		var yaw_node: Node3D = neck if is_free_looking else body
		yaw_node.rotate_y(deg_to_rad(-motion.relative.x * MOUSE_SENS))
		if INVERT_Y_AXIS:
			head.rotate_x(deg_to_rad(motion.relative.y * MOUSE_SENS))
		else:
			head.rotate_x(deg_to_rad(-motion.relative.y * MOUSE_SENS))
		head.rotation.x = clamp(head.rotation.x, deg_to_rad(-90.0), deg_to_rad(90.0))


class MouseEventSink:
	var player: FakePlayer
	var events: Array[InputEvent] = []

	func _init(fake_player: FakePlayer) -> void:
		player = fake_player

	func send(event: InputEventMouseMotion) -> void:
		events.append(event.duplicate())
		player._input(event)


class InteractionProvider:
	var calls: int = 0
	var interactions: Array = []
	var reveal_on_call: int = -1

	func get_interactions() -> Array:
		calls += 1
		if calls == reveal_on_call:
			return [{
				"action": "interact",
				"binding": "E",
				"prompt": "Switch circuit C on",
			}]
		return interactions


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	var probe: Node = AIPlayInteractionProbe.new()
	root.add_child(probe)
	var player := FakePlayer.new()
	root.add_child(player)
	var event_sink := MouseEventSink.new(player)
	probe.player = player
	probe.input_sender = event_sink.send
	await process_frame

	var unavailable_probe: Node = AIPlayInteractionProbe.new()
	root.add_child(unavailable_probe)
	_assert(
		await unavailable_probe.probe(0.5, 0.5)
			== {"status": "error", "error": "interaction probe is unavailable"},
		"missing player returns a bounded error",
	)
	unavailable_probe.player = player
	unavailable_probe.interaction_provider = func() -> Array: return []
	var original_sensitivity: float = player.MOUSE_SENS
	player.MOUSE_SENS = 0.0
	_assert(
		await unavailable_probe.probe(0.5, 0.5)
			== {"status": "error", "error": "interaction probe is unavailable"},
		"zero sensitivity returns a bounded error",
	)
	player.MOUSE_SENS = original_sensitivity
	unavailable_probe.queue_free()

	var centered: Vector2 = probe.target_rotation_degrees(0.5, 0.5, 75.0, 16.0 / 9.0)
	_assert(centered.is_zero_approx(), "center target has zero rotation")
	var left: Vector2 = probe.target_rotation_degrees(0.25, 0.5, 75.0, 16.0 / 9.0)
	var right: Vector2 = probe.target_rotation_degrees(0.75, 0.5, 75.0, 16.0 / 9.0)
	_assert(left.x < 0.0 and right.x > 0.0, "left and right targets have opposite yaw signs")
	var top: Vector2 = probe.target_rotation_degrees(0.5, 0.25, 75.0, 16.0 / 9.0)
	var bottom: Vector2 = probe.target_rotation_degrees(0.5, 0.75, 75.0, 16.0 / 9.0)
	_assert(top.y < 0.0 and bottom.y > 0.0, "top and bottom targets have opposite pitch signs")
	_assert(probe.SCAN_OFFSETS_DEGREES.size() == 9, "scan has exactly nine offsets")
	for offset: Vector2 in probe.SCAN_OFFSETS_DEGREES:
		_assert(
			offset.x >= -4.0 and offset.x <= 4.0 and offset.y >= -4.0 and offset.y <= 4.0,
			"scan offset stays within four degrees",
		)

	var aligned_provider := InteractionProvider.new()
	aligned_provider.reveal_on_call = 3
	probe.interaction_provider = aligned_provider.get_interactions
	event_sink.events.clear()
	var aligned_result: Dictionary = await probe.probe(0.5, 0.5)
	_assert(aligned_result == {
		"status": "completed",
		"type": "probe_interaction",
		"outcome": "aligned",
		"scan_steps": 1,
		"available_interactions": [{
			"action": "interact",
			"binding": "E",
			"prompt": "Switch circuit C on",
		}],
	}, "probe returns the public prompt after the target settles")
	_assert(
		aligned_provider.calls == probe.INTERACTION_SETTLE_CHECKS,
		"probe polls a stable orientation for bounded post-physics frames",
	)
	_assert(_contains_no_interaction_actions(event_sink.events), "probe never emits interaction actions")
	_assert(
		_all_mouse_events_use_device(event_sink.events, probe.SYNTHETIC_DEVICE_ID),
		"probe emits only dedicated synthetic mouse input",
	)

	var missing_provider := InteractionProvider.new()
	probe.interaction_provider = missing_provider.get_interactions
	event_sink.events.clear()
	player.is_free_looking = true
	var starting_yaw: float = player.camera.global_rotation_degrees.y
	var starting_pitch: float = player.head.rotation_degrees.x
	var missing_result: Dictionary = await probe.probe(0.5, 0.5)
	_assert(
		missing_result == {
			"status": "completed",
			"type": "probe_interaction",
			"outcome": "not_found",
			"scan_steps": 9,
		},
		"probe reports not found after all nine scan steps",
	)
	_assert(
		missing_provider.calls
		== probe.SCAN_OFFSETS_DEGREES.size() * probe.INTERACTION_SETTLE_CHECKS,
		"probe performs only bounded settle checks for each scan step",
	)
	var missing_mouse_events: Array[InputEventMouseMotion] = _mouse_events(event_sink.events)
	_assert(
		missing_mouse_events.size() == probe.SCAN_OFFSETS_DEGREES.size() + 1,
		"not found sends a final restoration mouse event",
	)
	_assert(
		not missing_mouse_events.back().relative.is_zero_approx(),
		"final mouse event restores the starting orientation",
	)
	_assert(
		is_equal_approx(player.camera.global_rotation_degrees.y, starting_yaw)
		and is_equal_approx(player.head.rotation_degrees.x, starting_pitch),
		"not found restoration returns a free-look camera to the starting orientation",
	)
	player.is_free_looking = false
	_assert(_contains_no_interaction_actions(event_sink.events), "not found probe never emits interaction actions")

	var cancelled_provider := InteractionProvider.new()
	probe.interaction_provider = cancelled_provider.get_interactions
	event_sink.events.clear()
	probe.call_deferred("cancel", "escape_stop")
	var cancelled_result: Dictionary = await probe.probe(0.5, 0.5)
	_assert(
		cancelled_result == {"status": "cancelled", "reason": "escape_stop"},
		"cancel returns the supplied cancellation reason",
	)
	_assert(cancelled_provider.calls == 0, "cancel prevents interaction checks after the pending frame")
	_assert(_contains_no_interaction_actions(event_sink.events), "cancelled probe never emits interaction actions")

	probe.queue_free()
	player.queue_free()
	if _failures.is_empty():
		print("AIPlay interaction probe tests passed")
		quit(0)
	else:
		for failure: String in _failures:
			push_error(failure)
		quit(1)


func _mouse_events(events: Array[InputEvent]) -> Array[InputEventMouseMotion]:
	var result: Array[InputEventMouseMotion] = []
	for event: InputEvent in events:
		if event is InputEventMouseMotion:
			result.append(event as InputEventMouseMotion)
	return result


func _all_mouse_events_use_device(events: Array[InputEvent], device_id: int) -> bool:
	var mouse_events: Array[InputEventMouseMotion] = _mouse_events(events)
	if mouse_events.is_empty():
		return false
	for event: InputEventMouseMotion in mouse_events:
		if event.device != device_id:
			return false
	return true


func _contains_no_interaction_actions(events: Array[InputEvent]) -> bool:
	for event: InputEvent in events:
		if event is InputEventAction:
			var action := event as InputEventAction
			if action.action in [&"interact", &"interact2"]:
				return false
	return true


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append("FAILED: %s" % label)
