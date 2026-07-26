extends SceneTree

var failures := 0

func _initialize() -> void:
	call_deferred("_run")


func _run() -> void:
	_test_home_scene_structure()
	_test_scene_trash_bin_accepts_held_trash()
	if failures == 0:
		print("Daily routine scene tests passed")
		quit(0)
	else:
		push_error("%d Daily routine scene test(s) failed" % failures)
		quit(1)

func _test_home_scene_structure() -> void:
	var packed: PackedScene = load("res://dailyroutine/scenes/home_daily_routine.tscn")
	_assert(packed != null, "home daily routine scene loads")
	if packed == null:
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	_assert(scene.get_node_or_null("Entryway") != null, "scene has entryway")
	_assert(scene.get_node_or_null("LivingRoom") != null, "scene has living room")
	_assert(scene.get_node_or_null("Kitchen") != null, "scene has kitchen")
	_assert(scene.get_node_or_null("Bedroom") != null, "scene has bedroom")
	_assert(_label_text(scene, "Entryway/RoomLabel") == "Entryway", "entryway has readable location label")
	_assert(_label_text(scene, "LivingRoom/RoomLabel") == "Living Room", "living room has readable location label")
	_assert(_label_text(scene, "Kitchen/RoomLabel") == "Kitchen", "kitchen has readable location label")
	_assert(_label_text(scene, "Bedroom/RoomLabel") == "Bedroom", "bedroom has readable location label")
	_assert(scene.get_node_or_null("Walls/MiddleWall") != null, "scene has left middle wall")
	_assert(scene.get_node_or_null("Walls/CenterMiddleWall") != null, "scene has center middle wall")
	_assert(scene.get_node_or_null("Walls/RightMiddleWall") != null, "scene has right middle wall")
	_assert(scene.get_node_or_null("Walls/RoomSplitWall") != null, "scene has bedroom kitchen split wall")
	_assert(scene.get_node_or_null("Walls/EntrySplitWallBack") != null, "scene has living entry split wall")
	_assert(scene.get_node_or_null("Entryway/StartHint") == null, "entryway no longer has start hint")
	_assert(scene.get_node_or_null("LivingRoom/StartHint") == null, "living room no longer has interactive start hint")
	_assert(_hud_explains_rules(scene), "HUD shows the rules without requiring readable interaction")
	_assert(scene.get_node_or_null("Entryway/PickupSpot") == null, "entryway no longer has front-door pickup box")
	_assert(scene.get_node_or_null("Entryway/FrontDoor") == null, "entryway no longer has front door mesh")
	_assert(scene.get_node_or_null("Entryway/DoorToLivingRoom") == null, "entryway no longer has a living room door")
	_assert(scene.get_node_or_null("LivingRoom/DoorToKitchen") == null, "living room no longer has a kitchen door")
	_assert(scene.get_node_or_null("LivingRoom/DoorToBedroom") == null, "living room no longer has a bedroom door")
	_assert(scene.get_node_or_null("Entryway/PaperTrashEntry") != null, "entryway has a loose trash candidate")
	_assert(scene.get_node_or_null("LivingRoom/PaperTrashLivingRoom") != null, "living room has a loose trash candidate")
	_assert(scene.get_node_or_null("Kitchen/FridgeMilk") != null, "kitchen has milk interaction")
	_assert(scene.get_node_or_null("Kitchen/FridgeMilk/MilkCarton") != null, "milk is represented by a carton")
	_assert(_fridge_uses_addon_container(scene), "kitchen uses addon fridge container with animated doors")
	_assert(_furniture_blockers_are_configured(scene), "large furniture has physical blockers")
	_assert(_milk_is_inside_fridge(scene), "milk carton starts inside the fridge")
	_assert(_milk_interaction_requires_open_fridge(scene), "milk can only be interacted with after the fridge opens")
	_assert(scene.get_node_or_null("Kitchen/BreakfastSpot") == null, "kitchen does not use breakfast spot gate")
	_assert(scene.get_node_or_null("Kitchen/KitchenTrashBin") == null, "kitchen no longer has trash bin")
	_assert(scene.get_node_or_null("LivingRoom/LivingRoomTrashBin") != null, "living room has trash bin")
	_assert(_trash_bin_interaction_point_is_shifted_left(scene), "trash bin interaction point is shifted left from the root")
	_assert(scene.get_node_or_null("Bedroom/BedroomTrashBin") == null, "bedroom no longer has trash bin")
	_assert(scene.get_node_or_null("TrashRandomizer") != null, "scene has random trash selector")
	_assert(scene.get_node_or_null("LivingRoom/FinishButton") != null, "living room has finish button beside trash bin")
	_assert(_active_trash_count(scene) == 4, "home has four active loose trash items")
	_assert(_loose_trash_is_visible_enough(scene), "loose trash is large and raised enough to see on the floor")
	_assert(_loose_trash_is_in_open_floor_positions(scene), "loose trash candidates are placed in open floor positions")
	_assert(scene.get_node_or_null("HomeRoutineTimeSystem") != null, "scene has time system")
	_assert(scene.get_node_or_null("DailyRoutineManager") != null, "scene has routine manager")
	_assert(scene.get_node_or_null("HUD") != null, "scene has HUD")
	_assert(scene.get_node_or_null("HUD/Crosshair/CrosshairTexture") != null, "HUD has center crosshair")
	_assert(scene.get_node_or_null("HUD/InteractionPrompt/PromptLabel") != null, "HUD has interaction prompt")
	_assert(scene.get_node_or_null("HUD/HintPanel/HintLabel") != null, "HUD has hint prompt")
	_assert(scene.get_node_or_null("HUD/Panel/MarginContainer/VBoxContainer/HoldingLabel") != null, "HUD shows held item status")
	_assert(scene.get_node_or_null("HUD/Panel/MarginContainer/VBoxContainer/RulesLabel") != null, "HUD has persistent rules text")
	var trash_label := _label_text_2d(scene, "HUD/Panel/MarginContainer/VBoxContainer/TrashLabel")
	_assert(trash_label.begins_with("总垃圾："), "HUD shows total trash count")
	_assert(trash_label.contains("已扔："), "HUD shows disposed trash count")
	_assert(not trash_label.contains("含过期牛奶"), "HUD does not spell out that milk is counted as trash")
	_assert(not _label_text_2d(scene, "HUD/Panel/MarginContainer/VBoxContainer/ObjectiveLabel").contains("牛奶"), "HUD objective does not mention milk")
	_assert(scene.get_node_or_null("CogitoPlayer") != null, "scene has player")
	_assert(scene.get_node_or_null("AIPlayController") != null, "scene has AIPlay controller")
	_assert(scene.get_node_or_null("AIPlayController/DailyRoutineMonitor") != null, "scene has daily routine AI monitor")
	_assert(scene.get_node_or_null("AIPlayController/DailyRoutineMonitor/GameOverScreen") != null, "scene has AI game-over screen")
	var ai_controller := scene.get_node_or_null("AIPlayController")
	if ai_controller != null:
		_assert(ai_controller.get("auto_start") == false, "AI Play is opt-in")
		_assert(str(ai_controller.get("host")) == "127.0.0.1", "AI Play uses loopback host")
	_assert(_player_starts_in_living_room(scene), "player starts in living room")
	scene.queue_free()

func _test_scene_trash_bin_accepts_held_trash() -> void:
	var packed: PackedScene = load("res://dailyroutine/scenes/home_daily_routine.tscn")
	_assert(packed != null, "home daily routine scene loads for trash interaction")
	if packed == null:
		return
	var scene := packed.instantiate()
	root.add_child(scene)
	var manager := scene.get_node_or_null("DailyRoutineManager")
	var trash := scene.get_node_or_null("Kitchen/PaperTrashA")
	var bin := scene.get_node_or_null("LivingRoom/LivingRoomTrashBin")
	var lid := scene.get_node_or_null("LivingRoom/LivingRoomTrashBin/Lid") as Node3D
	var player := scene.get_node_or_null("CogitoPlayer")
	var fridge_milk := scene.get_node_or_null("Kitchen/FridgeMilk")
	var fridge := scene.get_node_or_null("Kitchen/Fridge") as Node3D
	_assert(manager != null, "trash interaction has manager")
	_assert(trash != null, "trash interaction has paper trash")
	_assert(bin != null, "trash interaction has living room trash bin")
	_assert(lid != null, "trash bin has visible lid feedback")
	_assert(player != null, "trash interaction has player")
	_assert(fridge_milk != null, "fridge interaction has milk")
	_assert(fridge != null, "fridge interaction has addon fridge")
	if manager != null and trash != null and bin != null:
		if trash.has_method("set_spawned"):
			trash.set_spawned(true)
		trash.manager = manager
		bin.manager = manager
		trash.interact(null)
		_assert(manager.has_loose_trash, "paper trash interaction makes player hold trash")
		if player != null:
			player.routine_manager = manager
			player.position = Vector3(-5.8, 1.05, 3.6)
			player.drop_held_trash_to_nearby_bin_for_test()
		else:
			bin.interact(null)
		_assert(not manager.has_loose_trash, "trash bin interaction removes held trash")
		_assert(manager.collected_trash_count == 1, "trash bin interaction increments trash count")
		if lid != null:
			_assert(lid.rotation_degrees.x < -20.0, "trash bin lid opens when trash is placed")
	if player != null and fridge != null:
		player.interact_with_target_for_test(fridge)
		var fridge_open_amount := _addon_fridge_open_amount(fridge)
		_assert(
			fridge_open_amount > 1.45,
			"player interaction opens addon fridge doors to a readable angle, got %.3f; %s" % [
				fridge_open_amount,
				_fridge_debug(fridge),
			],
		)
		_assert(str(fridge.get("interaction_text")) == "拿过期牛奶", "open fridge offers expired milk pickup")
		if manager != null:
			player.routine_manager = manager
			player.interact_with_target_for_test(fridge)
			_assert(not manager.has_milk, "expired milk is not held as drinkable milk")
			_assert(manager.has_loose_trash, "open fridge interaction takes expired milk as trash")
			bin.interact(player)
			_assert(not manager.has_loose_trash, "living room bin accepts expired milk")
		if fridge.has_method("close"):
			fridge.close()
	scene.queue_free()

func _count_named_prefix(node: Node, prefix: String) -> int:
	var count := 0
	var node_name := str(node.name)
	if node_name.begins_with(prefix):
		count += 1
	for child in node.get_children():
		count += _count_named_prefix(child, prefix)
	return count

func _active_trash_count(scene: Node) -> int:
	var randomizer := scene.get_node_or_null("TrashRandomizer")
	if randomizer != null:
		if int(randomizer.get("active_trash_count")) == 0 and randomizer.has_method("randomize_trash"):
			randomizer.randomize_trash()
		return int(randomizer.get("active_trash_count"))
	var count := 0
	var trash_paths := [
		"Entryway/PaperTrashEntry",
		"LivingRoom/PaperTrashLivingRoom",
		"Kitchen/PaperTrashA",
		"Bedroom/PaperTrashBedroomA",
	]
	for trash_path in trash_paths:
		var trash := scene.get_node_or_null(trash_path)
		if trash != null and trash.visible:
			count += 1
	return count

func _loose_trash_is_visible_enough(scene: Node) -> bool:
	var trash_paths := [
		"Entryway/PaperTrashEntry",
		"LivingRoom/PaperTrashLivingRoom",
		"Kitchen/PaperTrashA",
		"Bedroom/PaperTrashBedroomA",
	]
	for trash_path in trash_paths:
		var trash := scene.get_node_or_null(trash_path) as Node3D
		var mesh_node := scene.get_node_or_null(trash_path + "/Mesh") as MeshInstance3D
		if trash == null or mesh_node == null:
			return false
		var mesh := mesh_node.mesh as SphereMesh
		if mesh == null or mesh.radius < 0.32 or mesh.height < 0.42:
			return false
		if trash.position.y < 0.32:
			return false
	return true

func _loose_trash_is_in_open_floor_positions(scene: Node) -> bool:
	var entry := scene.get_node_or_null("Entryway/PaperTrashEntry") as Node3D
	var living := scene.get_node_or_null("LivingRoom/PaperTrashLivingRoom") as Node3D
	var kitchen_a := scene.get_node_or_null("Kitchen/PaperTrashA") as Node3D
	var bedroom_a := scene.get_node_or_null("Bedroom/PaperTrashBedroomA") as Node3D
	if entry == null or living == null or kitchen_a == null or bedroom_a == null:
		return false
	return entry.position.x > 4.1 \
		and entry.position.z > 2.4 \
		and living.position.x < -4.4 \
		and living.position.z > 2.0 \
		and kitchen_a.position.z > -1.8 \
		and bedroom_a.position.x < -6.0 \
		and bedroom_a.position.z < -3.0

func _label_text(scene: Node, path: String) -> String:
	var label := scene.get_node_or_null(path) as Label3D
	return "" if label == null else label.text

func _label_text_2d(scene: Node, path: String) -> String:
	var label := scene.get_node_or_null(path) as Label
	return "" if label == null else label.text

func _hud_explains_rules(scene: Node) -> bool:
	var content := _label_text_2d(scene, "HUD/Panel/MarginContainer/VBoxContainer/RulesLabel")
	return content.contains("牛奶") \
		and content.contains("过期") \
		and not content.contains("牛奶，它现在是垃圾") \
		and not content.contains("把过期牛奶") \
		and content.contains("客厅垃圾桶") \
		and content.contains("4 个散落垃圾") \
		and content.contains("冰箱关闭") \
		and content.contains("完成任务")

func _furniture_blockers_are_configured(scene: Node) -> bool:
	var blocker_paths := [
		"LivingRoom/SofaCollision",
		"LivingRoom/LowTableCollision",
		"Kitchen/CabinetACollision",
		"Kitchen/SinkCollision",
		"Kitchen/FridgeCollision",
		"Bedroom/BedCollision",
		"Bedroom/BedCabinetCollision",
	]
	for blocker_path in blocker_paths:
		var body := scene.get_node_or_null(blocker_path) as StaticBody3D
		if body == null:
			return false
		var collision_shape := body.get_node_or_null("CollisionShape3D") as CollisionShape3D
		if collision_shape == null:
			return false
		var shape := collision_shape.shape as BoxShape3D
		if shape == null:
			return false
		if shape.size.x <= 0.0 or shape.size.y <= 0.0 or shape.size.z <= 0.0:
			return false
	return true

func _door_is_interactive(door: Node) -> bool:
	if door == null:
		return false
	var cogito_door := door.get_node_or_null("Door")
	var collision := door.get_node_or_null("Door/CollisionShape3D") as CollisionShape3D
	return cogito_door != null \
		and cogito_door.has_method("interact") \
		and not cogito_door.is_open \
		and collision != null \
		and not collision.disabled

func _player_starts_in_living_room(scene: Node) -> bool:
	var player := scene.get_node_or_null("CogitoPlayer") as Node3D
	if player == null:
		return false
	var player_position := player.position
	return player_position.x < 0.0

func _trash_bin_interaction_point_is_shifted_left(scene: Node) -> bool:
	var collision := scene.get_node_or_null("LivingRoom/LivingRoomTrashBin/CollisionShape3D") as CollisionShape3D
	if collision == null:
		return false
	return collision.position.x < -0.25

func _fridge_uses_addon_container(scene: Node) -> bool:
	var fridge := scene.get_node_or_null("Kitchen/Fridge")
	if fridge == null:
		return false
	return fridge.has_method("interact") \
		and fridge.has_method("open") \
		and fridge.has_method("close") \
		and str(fridge.get_script()).contains("addon_fridge_interaction.gd") \
		and fridge.get_node_or_null("FridgeDoorLeft") != null \
		and fridge.get_node_or_null("FridgeDoorRight") != null \
		and fridge.get_node_or_null("AnimationPlayer") != null \
		and _node_script_is_disabled(fridge, "BasicInteraction") \
		and _node_script_is_disabled(fridge, "InventoryCheckerWIN") \
		and _node_script_is_disabled(fridge, "InventoryCheckerFAIL") \
		and _node_script_is_disabled(fridge, "QuestUpdaterWIN") \
		and _node_script_is_disabled(fridge, "QuestUpdaterFAIL")

func _node_script_is_disabled(parent: Node, child_name: String) -> bool:
	var child := parent.get_node_or_null(child_name)
	return child != null and child.get_script() == null

func _addon_fridge_open_amount(fridge: Node) -> float:
	var left := fridge.get_node_or_null("FridgeDoorLeft") as Node3D
	var right := fridge.get_node_or_null("FridgeDoorRight") as Node3D
	if left == null or right == null:
		return 0.0
	var left_mesh := left.get_node_or_null("doorLeft") as Node3D
	var right_mesh := right.get_node_or_null("doorRight") as Node3D
	return maxf(
		maxf(absf(left.rotation.y), absf(right.rotation.y)),
		maxf(
			absf(left_mesh.rotation.y) if left_mesh != null else 0.0,
			absf(right_mesh.rotation.y) if right_mesh != null else 0.0,
		),
	)

func _fridge_debug(fridge: Node) -> String:
	var child_names: Array[String] = []
	for child: Node in fridge.get_children():
		child_names.append(str(child.name))
	var left := fridge.get_node_or_null("FridgeDoorLeft") as Node3D
	var right := fridge.get_node_or_null("FridgeDoorRight") as Node3D
	return "script=%s is_open=%s angle=%s left=%s right=%s children=%s" % [
		str(fridge.get_script()),
		str(fridge.get("is_open")),
		str(fridge.get("open_angle_radians")),
		str(left.rotation if left != null else null),
		str(right.rotation if right != null else null),
		",".join(child_names),
	]

func _milk_is_inside_fridge(scene: Node) -> bool:
	var fridge := scene.get_node_or_null("Kitchen/Fridge") as Node3D
	var milk := scene.get_node_or_null("Kitchen/FridgeMilk") as Node3D
	if fridge == null or milk == null:
		return false
	var fridge_position := fridge.global_position if fridge.is_inside_tree() else fridge.position
	var milk_position := milk.global_position if milk.is_inside_tree() else milk.position
	var horizontal_offset := Vector2(fridge_position.x, fridge_position.z).distance_to(Vector2(milk_position.x, milk_position.z))
	var not_on_center_seam := absf(milk_position.x - (fridge_position.x + 0.65)) > 0.18
	return horizontal_offset <= 0.65 and milk_position.y >= 0.5 and milk_position.y <= 2.4 and not_on_center_seam

func _milk_interaction_requires_open_fridge(scene: Node) -> bool:
	var fridge := scene.get_node_or_null("Kitchen/Fridge")
	var milk := scene.get_node_or_null("Kitchen/FridgeMilk") as StaticBody3D
	if fridge == null or milk == null:
		return false
	if milk.has_method("_sync_visibility"):
		milk._sync_visibility()
	if milk.collision_layer != 0:
		return false
	if fridge.has_method("open"):
		fridge.open()
	if milk.has_method("_sync_visibility"):
		milk._sync_visibility()
	return milk.collision_layer != 0

func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
