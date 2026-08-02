extends SceneTree

var _failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var lobby_scene: PackedScene = load(
		"res://addons/cogito/DemoScenes/COGITO_3_Lobby.tscn"
	)
	_assert(lobby_scene != null, "Lobby scene loads")
	if lobby_scene == null:
		_finish()
		return

	var lobby: Node = lobby_scene.instantiate()
	root.add_child(lobby)
	await process_frame

	var monitor: Node = lobby.get_node_or_null(
		"AIPlayController/FindKeyMonitor"
	)
	_assert(monitor != null, "Lobby includes FindKeyMonitor")
	if monitor == null:
		lobby.queue_free()
		await process_frame
		_finish()
		return
	_assert(
		monitor.LOCATION_IDS == [
			"laptop_desk",
			"archive_sofa",
			"meeting_table",
			"tv_coffee_table",
		],
		"find_key exposes exactly the four non-cubicle locations",
	)
	_assert(
		lobby.get_node_or_null("FindKeyMarkers/DesktopDeskAnchor") == null,
		"Lobby does not retain the removed desktop key anchor",
	)

	var seen_locations: Array[String] = []
	for seed_value: int in range(1, 129):
		monitor.configure_round(seed_value)
		var snapshot: Dictionary = monitor.get_round_snapshot()
		var location: String = snapshot["location"]
		_assert(
			location in monitor.LOCATION_IDS,
			"location is allowlisted",
		)
		_assert(
			monitor.get_act_request_limit() == 50,
			"every selected key location uses the fixed 50-request limit",
		)
		_assert(
			snapshot["task_text"]
				== monitor.LOCATION_TASK_TEXT[location],
			"task card matches the selected key location",
		)
		_assert(
			snapshot["task_text"] in monitor.task_card.readable_content,
			"visible task card contains only the selected location clue",
		)
		for required_instruction: String in [
			"任务目标",
			"位置线索",
			"操作",
			"完成条件",
			"只看到钥匙不算完成",
		]:
			_assert(
				monitor.task_card.readable_content.contains(required_instruction),
				"task card clearly explains %s" % required_instruction,
			)
		_assert(
			lobby.find_children(
				"Pickup_Key",
				"",
				true,
				false,
			).size() == 1,
			"the scene contains exactly one key",
		)
		for distance: float in snapshot["spawn_distances"]:
			_assert(
				snapshot["selected_spawn_distance"] + 0.001
					>= distance,
				"the selected spawn is farthest from the key",
			)
		var task_distance: float = (
			monitor.player.global_position.distance_to(
				monitor.task_card.get_parent_node_3d().global_position
			)
		)
		_assert(
			task_distance >= 1.0 and task_distance <= 2.0,
			"the task card remains one to two meters from spawn",
		)
		if location not in seen_locations:
			seen_locations.append(location)

	_assert(
		seen_locations.size() == monitor.LOCATION_IDS.size(),
		"fixed seed sample reaches all four key locations",
	)
	var task_ui := monitor.task_card.get_node("ReadableUi") as Control
	var task_scroll := monitor.task_card.get_node(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var task_content_container := monitor.task_card.get_node(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer"
	) as VBoxContainer
	task_ui.show()
	await process_frame
	await process_frame
	_assert(
		task_scroll.vertical_scroll_mode == ScrollContainer.SCROLL_MODE_DISABLED,
		"find-key task card does not require scrolling",
	)
	_assert(
		task_content_container.get_combined_minimum_size().y <= task_scroll.size.y,
		"find-key task card content fits without clipping",
	)
	task_ui.hide()

	monitor.configure_round(123456)
	var terminal_results: Array[Dictionary] = []
	monitor.game_finished.connect(
		func(outcome: String, reason: String) -> void:
			terminal_results.append({
				"outcome": outcome,
				"reason": reason,
			})
	)
	var pickup: Node = monitor.key.get_node("PickupComponent")
	pickup.was_interacted_with.emit("Pick up", "interact")
	pickup.was_interacted_with.emit("Pick up", "interact")
	_assert(
		terminal_results == [{
			"outcome": "success",
			"reason": "key_picked_up",
		}],
		"successful pickup ends the round exactly once",
	)

	lobby.queue_free()
	await process_frame
	_finish()


func _finish() -> void:
	if _failures.is_empty():
		print("AIPlay find-key monitor test passed")
		quit(0)
		return
	for failure: String in _failures:
		push_error(failure)
	quit(1)


func _assert(condition: bool, label: String) -> void:
	if not condition:
		_failures.append(label)
