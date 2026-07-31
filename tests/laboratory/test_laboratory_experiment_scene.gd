extends SceneTree

const LABORATORY_PATH := "res://addons/cogito/DemoScenes/COGITO_4_Laboratory.tscn"
const STATION_PATH := "NavigationRegion3D/SYSTEMIC_PROPERTIES/LaboratoryExperiment"
const REQUIRED_BUTTONS: Array[String] = [
	"Controls/BatteryAlpha",
	"Controls/BatteryBeta",
	"Controls/BatteryGamma",
	"Controls/SampleA",
	"Controls/SampleB",
	"Controls/SampleC",
	"Controls/TreatmentDry",
	"Controls/TreatmentWet",
	"Controls/TreatmentHeated",
	"Controls/InstallBar",
	"Controls/RunExperiment",
	"Controls/ResetSetup",
]

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
		for anchor_group: String in ["BatteryAnchors", "BarAnchors", "TaskCardAnchors"]:
			_assert(station.get_node_or_null(anchor_group) != null, "%s exists" % anchor_group)

	_assert(laboratory.get_node_or_null("Player") != null, "existing player remains present")
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
		running_station.get_node("StatusPanel").text.contains("PROTOCOL:"),
		"station initializes its live status display",
	)
	running_station.get_node("Controls/BatteryAlpha").pressed.emit()
	running_station.get_node("Controls/SampleB").pressed.emit()
	running_station.get_node("Controls/TreatmentWet").pressed.emit()
	running_station.get_node("Controls/InstallBar").pressed.emit()
	var running_manager := running_station.get_node("Manager")
	_assert(running_manager.battery_installed == "alpha", "battery button is wired")
	_assert(running_manager.selected_sample == "b", "sample button is wired")
	_assert(running_manager.sample_state == "wet", "treatment button is wired")
	_assert(running_manager.metal_bar_installed, "bar button is wired")
	_assert(
		running_station.get_node("TaskCard/ReadableComponent").label_content.text
		== running_manager.task_card_text(),
		"task card UI shows the generated public clues",
	)
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
