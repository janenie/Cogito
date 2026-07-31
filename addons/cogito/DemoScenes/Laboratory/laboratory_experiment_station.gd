class_name LaboratoryExperimentStation
extends Node3D

@onready var manager: Node = $Manager
@onready var task_card: Node = $TaskCard/ReadableComponent
@onready var status_panel: Label3D = $StatusPanel
@onready var history_panel: Label3D = $HistoryPanel
@onready var experiment_lamp: MeshInstance3D = $ExperimentLamp
@onready var treatment_effect: OmniLight3D = $TreatmentEffect

var _lamp_material := StandardMaterial3D.new()


func _ready() -> void:
	_connect_button("BatteryAlpha", manager.select_battery.bind("alpha"))
	_connect_button("BatteryBeta", manager.select_battery.bind("beta"))
	_connect_button("BatteryGamma", manager.select_battery.bind("gamma"))
	_connect_button("SampleA", manager.select_sample.bind("a"))
	_connect_button("SampleB", manager.select_sample.bind("b"))
	_connect_button("SampleC", manager.select_sample.bind("c"))
	_connect_button("TreatmentDry", manager.select_treatment.bind("dry"))
	_connect_button("TreatmentWet", manager.select_treatment.bind("wet"))
	_connect_button("TreatmentHeated", manager.select_treatment.bind("heated"))
	_connect_button("InstallBar", manager.set_metal_bar_installed.bind(true))
	_connect_button("RunExperiment", manager.run_experiment)
	_connect_button("ResetSetup", manager.reset_setup)
	manager.public_state_changed.connect(_refresh_display)
	manager.round_finished.connect(_on_round_finished)
	_lamp_material.albedo_color = Color(0.08, 0.09, 0.1)
	_lamp_material.emission_enabled = true
	experiment_lamp.material_override = _lamp_material
	task_card.readable_title = "Laboratory Experiment Protocol"
	task_card.readable_content = manager.task_card_text()
	task_card.label_title.text = task_card.readable_title
	task_card.label_content.text = task_card.readable_content
	_refresh_display()


func _connect_button(button_name: String, callback: Callable) -> void:
	var button := get_node("Controls/%s" % button_name)
	button.pressed.connect(callback)


func _refresh_display() -> void:
	var public_state: Dictionary = manager.ai_play_public_state()
	status_panel.text = (
		"PROTOCOL: %s\nENV: %s\nATTEMPTS: %d / %d\n"
		+ "BATTERY: %s   SAMPLE: %s   STATE: %s\nBAR: %s   STATUS: %s"
	) % [
		str(public_state.protocol).replace("_", " ").to_upper(),
		str(public_state.environment).replace("_", " ").to_upper(),
		public_state.attempts_used,
		public_state.attempts_limit,
		str(public_state.battery_installed).to_upper(),
		str(public_state.selected_sample).to_upper(),
		str(public_state.sample_state).to_upper(),
		"INSTALLED" if public_state.metal_bar_installed else "MISSING",
		manager.status_code.replace("_", " ").to_upper(),
	]
	history_panel.text = _history_text()
	_update_lamp(str(public_state.last_lamp))
	_update_treatment_effect(str(public_state.sample_state))


func _history_text() -> String:
	if manager.result_history.is_empty():
		return "MEASUREMENTS\nNo completed experiments"
	var lines: Array[String] = ["MEASUREMENTS"]
	for index: int in manager.result_history.size():
		var result: Dictionary = manager.result_history[index]
		lines.append(
			"%d  PWR %s  CUR %s  %s  TEMP %s  LAMP %s" % [
				index + 1,
				str(result.power).to_upper(),
				str(result.current).to_upper(),
				str(result.stability).to_upper(),
				str(result.temperature).to_upper(),
				str(result.lamp).to_upper(),
			]
		)
	return "\n".join(lines)


func _update_lamp(lamp_state: String) -> void:
	var color := Color(0.08, 0.09, 0.1)
	match lamp_state:
		"dim":
			color = Color(0.35, 0.32, 0.12)
		"flicker":
			color = Color(0.95, 0.34, 0.08)
		"stable":
			color = Color(0.25, 1.0, 0.52)
	_lamp_material.albedo_color = color
	_lamp_material.emission = color
	_lamp_material.emission_energy_multiplier = 3.0 if lamp_state != "none" else 0.0


func _update_treatment_effect(treatment: String) -> void:
	treatment_effect.visible = treatment != "dry"
	treatment_effect.light_color = (
		Color(0.15, 0.55, 1.0) if treatment == "wet" else Color(1.0, 0.22, 0.05)
	)


func _on_round_finished(outcome: String, reason: String) -> void:
	status_panel.text += "\nRESULT: %s - %s" % [
		outcome.to_upper(),
		reason.replace("_", " ").to_upper(),
	]
