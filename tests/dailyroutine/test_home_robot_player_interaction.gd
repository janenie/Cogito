extends SceneTree

var failures := 0


func _initialize() -> void:
	call_deferred("_run_tests")


func _run_tests() -> void:
	_test_player_resolves_interactables_and_prompts()
	if failures == 0:
		print("Home robot player interaction tests passed")
		quit(0)
	else:
		push_error("%d home robot player interaction test(s) failed" % failures)
		quit(1)

func _test_player_resolves_interactables_and_prompts() -> void:
	var PlayerScript = load("res://dailyroutine/scripts/home_robot_player.gd")
	_assert(PlayerScript != null, "home robot player script loads")
	if PlayerScript == null:
		return

	var player = PlayerScript.new()
	root.add_child(player)

	_assert(player.has_method("resolve_interaction_target_for_test"), "player exposes interaction target resolver")
	_assert(player.has_method("get_interaction_prompt_for_test"), "player exposes interaction prompt resolver")
	_assert(player.has_method("_movement_direction_from_input"), "player exposes movement conversion")
	if player.has_method("_movement_direction_from_input"):
		var precise_direction: Vector3 = player._movement_direction_from_input(Vector2(0.0, -0.25))
		_assert(
			is_equal_approx(precise_direction.length(), 0.25),
			"player preserves fractional movement strength",
		)

	var InteractableScript = load("res://tests/dailyroutine/fixtures/fake_interactable.gd")
	_assert(InteractableScript != null, "fake interactable script loads")
	if InteractableScript == null:
		player.queue_free()
		return
	var target_node = InteractableScript.new()
	root.add_child(target_node)
	if player.has_method("resolve_interaction_target_for_test"):
		var target = player.resolve_interaction_target_for_test(target_node)
		_assert(target == target_node, "player resolves interactable collision body")
	if player.has_method("get_interaction_prompt_for_test"):
		var prompt: String = player.get_interaction_prompt_for_test(target_node)
		_assert(prompt == "Open", "prompt uses interactable interaction_text")

	var ReadableHintScript = load("res://tests/dailyroutine/fixtures/fake_readable_hint.gd")
	_assert(ReadableHintScript != null, "fake readable hint script loads")
	if ReadableHintScript != null:
		var readable_hint = ReadableHintScript.new()
		root.add_child(readable_hint)
		readable_hint._ready()
		var readable_target = player.resolve_interaction_target_for_test(readable_hint)
		_assert(readable_target == readable_hint, "player resolves hint root with readable component child")
		_assert(player.get_interaction_prompt_for_test(readable_hint) == "Read rules", "player prompts readable hint action")
		readable_hint.queue_free()

	var DoorScript = load("res://tests/dailyroutine/fixtures/fake_cogito_door.gd")
	_assert(DoorScript != null, "fake cogito door script loads")
	if DoorScript != null and player.has_method("interact_with_target_for_test"):
		var door = DoorScript.new()
		root.add_child(door)
		player.interact_with_target_for_test(door)
		_assert(door.is_open, "player opens cogito-style door through open_door")
		_assert(not door.interact_called, "player does not call cogito door interact directly")
		player.interact_with_target_for_test(door)
		_assert(not door.is_open, "player closes cogito-style door through close_door")
		door.queue_free()

	target_node.queue_free()
	player.queue_free()

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
