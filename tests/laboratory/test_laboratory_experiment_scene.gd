extends SceneTree

const LABORATORY_PATH := "res://addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn"
const STATION_PATH := "NavigationRegion3D/SYSTEMIC_PROPERTIES/LaboratoryExperiment"
const REQUIRED_BUTTONS: Array[String] = [
	"Controls/ResetSetup",
]
const REQUIRED_SLOTS := {
	"AssemblySlots/BatterySlot": "battery",
	"AssemblySlots/SampleSlot": "sample",
	"AssemblySlots/TreatmentSlot": "treatment",
	"AssemblySlots/ConnectorSlot": "connector",
}

var failures := 0


func _initialize() -> void:
	var packed := load(LABORATORY_PATH) as PackedScene
	_assert(packed != null, "Laboratory scene loads")
	if packed == null:
		_finish()
		return
	var laboratory := packed.instantiate()
	var station := laboratory.get_node_or_null(STATION_PATH)
	_assert(station != null, "Laboratory contains the experiment station")
	if station != null:
		var manager := station.get_node_or_null("Manager")
		_assert(manager != null, "station contains manager")
		_assert(
			manager != null and manager.has_method("ai_play_public_state"),
			"station manager script is loaded",
		)
		_assert(station.get_node_or_null("TaskCard/ReadableComponent") != null, "station has readable task card")
		_assert(station.get_node_or_null("StatusPanel") != null, "station has status panel")
		_assert(station.get_node_or_null("HistoryPanel") != null, "station has history panel")
		_assert(station.get_node_or_null("ExperimentLamp") != null, "station has experiment lamp")
		_assert(station.get_node_or_null("TaskCardMarker") != null, "task card has a visible marker")
		_assert(station.get_node_or_null("ExperimentHUD") is CanvasLayer, "station has a screen HUD")
		for hud_path: String in [
			"ExperimentHUD/Layout/RulesPanel/Margin/Content/Title",
			"ExperimentHUD/Layout/RulesPanel/Margin/Content/Rules",
			"ExperimentHUD/Layout/StatePanel/Margin/Content/State",
			"ExperimentHUD/Layout/StatePanel/Margin/Content/History",
		]:
			_assert(station.get_node_or_null(hud_path) != null, "%s exists" % hud_path)
		for button_path: String in REQUIRED_BUTTONS:
			var button := station.get_node_or_null(button_path)
			_assert(button != null, "%s exists" % button_path)
			if button != null:
				var interaction := button.get_node_or_null("BasicInteraction")
				_assert(interaction != null, "%s is interactable" % button_path)
				_assert(
					interaction != null and interaction.input_map_action in ["interact", "interact2"],
					"%s uses an allowlisted AI action" % button_path,
				)
		for slot_path: String in REQUIRED_SLOTS:
			var slot := station.get_node_or_null(slot_path)
			_assert(slot != null, "%s exists" % slot_path)
			_assert(
				slot != null and slot.accepted_kind == REQUIRED_SLOTS[slot_path],
				"%s accepts the correct component kind" % slot_path,
			)
		for removed_button: String in [
			"Controls/RunExperiment",
			"Controls/BatteryAlpha",
			"Controls/SampleA",
			"Controls/TreatmentDry",
			"Controls/InstallBar",
		]:
			_assert(station.get_node_or_null(removed_button) == null, "%s was removed" % removed_button)
		for anchor_group: String in ["BatteryAnchors", "BarAnchors", "TaskCardAnchors"]:
			_assert(station.get_node_or_null(anchor_group) != null, "%s exists" % anchor_group)

	var player := laboratory.get_node_or_null("Player") as Node3D
	_assert(player != null, "existing player remains present")
	if player != null and station is Node3D:
		_assert(
			player.position.distance_to(station.position) <= 6.0,
			"player starts within sight of the experiment station",
		)
	for existing_path: String in [
		"NavigationRegion3D/SYSTEMIC_PROPERTIES/Cathode_A",
		"NavigationRegion3D/SYSTEMIC_PROPERTIES/Cathode_B",
		"NavigationRegion3D/SYSTEMIC_PROPERTIES/Cathode_C",
		"NavigationRegion3D/SYSTEMIC_PROPERTIES/SnapSlotBattery",
		"NavigationRegion3D/SYSTEMIC_PROPERTIES/SnapSlotMetalbar",
	]:
		_assert(laboratory.get_node_or_null(existing_path) != null, "%s remains present" % existing_path)
	laboratory.free()
	var station_scene := load(
		"res://addons/cogito/DemoScenes/Laboratory/laboratory_experiment_station.tscn"
	) as PackedScene
	var running_station := station_scene.instantiate()
	root.add_child(running_station)
	await process_frame
	_assert(
		running_station.get_node("StatusPanel").text.contains("实验："),
		"station initializes its Chinese live status display",
	)
	_assert(
		running_station.get_node("StatusPanel").text.contains("自动分析"),
		"status display directs the player to assemble before automatic analysis",
	)
	_assert(
		not running_station.get_node("StatusPanel").text.contains("PROTOCOL"),
		"3D status display has no English prompt",
	)
	_assert(
		running_station.get_node("HistoryPanel").text.contains("实验记录"),
		"3D measurement display is Chinese",
	)
	var running_manager := running_station.get_node("Manager")
	var candidates := running_station.get_node_or_null("Candidates")
	_assert(candidates != null, "station has a candidate container")
	if candidates != null:
		_assert(candidates.get_child_count() == 10, "station spawns ten physical candidates")
		var kinds := {"battery": 0, "sample": 0, "treatment": 0, "connector": 0}
		var example_components := {}
		for candidate: Node in candidates.get_children():
			kinds[candidate.component_kind] += 1
			if not example_components.has(candidate.component_kind):
				example_components[candidate.component_kind] = candidate
			var carry := candidate.get_node_or_null("CarryableComponent")
			_assert(carry != null, "%s is carryable" % candidate.name)
			_assert(
				carry != null and carry.input_map_action == "interact2",
				"%s uses interact2" % candidate.name,
			)
		_assert(kinds == {"battery": 3, "sample": 3, "treatment": 3, "connector": 1}, "candidate kinds are complete")
		for kind: String in ["battery", "sample", "treatment", "connector"]:
			var component: Node = example_components[kind]
			var slot: Node = running_station.get_node(
				"AssemblySlots/%sSlot" % kind.capitalize()
			)
			component.get_node("CarryableComponent").is_being_carried = true
			slot._on_body_entered(component)
			if kind == "battery":
				slot._on_body_exited(component)
				_assert(running_manager.battery_installed == "none", "removing a component clears its slot state")
				component.get_node("CarryableComponent").is_being_carried = true
				slot._on_body_entered(component)
		await process_frame
		_assert(running_manager.battery_installed != "none", "battery slot updates manager")
		_assert(running_manager.selected_sample != "none", "sample slot updates manager")
		_assert(running_manager.sample_state != "none", "treatment slot updates manager")
		_assert(running_manager.metal_bar_installed, "connector slot updates manager")
		_assert(running_manager.attempts_used == 1, "fourth component triggers automatic analysis")
	_assert(
		running_station.get_node("TaskCard/ReadableComponent").label_content.text
		== running_manager.task_card_text(),
		"task card UI shows the generated public clues",
	)
	_assert(
		running_station.get_node("TaskCard/ReadableComponent").label_title.text
		== "实验任务说明",
		"task card title is Chinese",
	)
	var hud_title := running_station.get_node(
		"ExperimentHUD/Layout/RulesPanel/Margin/Content/Title"
	) as Label
	var hud_rules := running_station.get_node(
		"ExperimentHUD/Layout/RulesPanel/Margin/Content/Rules"
	) as RichTextLabel
	var hud_state := running_station.get_node(
		"ExperimentHUD/Layout/StatePanel/Margin/Content/State"
	) as Label
	_assert(hud_title.text == "实验任务", "HUD title is Chinese")
	_assert(hud_title.get_theme_font_size("font_size") >= 32, "HUD title uses a large font")
	_assert(hud_rules.get_theme_font_size("normal_font_size") >= 24, "HUD rules use a large font")
	_assert(hud_rules.text.contains("游戏规则"), "HUD explains the rules in Chinese")
	_assert(hud_rules.text.contains("最多 3 次"), "HUD states the three-attempt limit")
	_assert(hud_rules.text.contains("寻找"), "HUD explains the physical search loop")
	_assert(hud_rules.text.contains("无需按住"), "HUD explains that carrying uses one E press")
	_assert(hud_rules.text.contains("自动分析"), "HUD explains automatic validation at the start bench")
	_assert(hud_state.text.contains("当前配置"), "HUD exposes current setup in Chinese")
	running_station.queue_free()
	_finish()


func _finish() -> void:
	if failures == 0:
		print("Laboratory experiment scene tests passed")
		quit(0)
	else:
		push_error("%d laboratory scene test(s) failed" % failures)
		quit(1)


func _assert(condition: bool, message: String) -> void:
	if not condition:
		failures += 1
		push_error(message)
