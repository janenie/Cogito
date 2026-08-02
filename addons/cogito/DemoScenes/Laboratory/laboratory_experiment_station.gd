class_name LaboratoryExperimentStation
extends Node3D

const ComponentScene = preload(
	"res://addons/cogito/DemoScenes/Laboratory/laboratory_experiment_component.tscn"
)
const COMPONENT_SPECS: Array[Dictionary] = [
	{"kind": "battery", "id": "alpha", "label": "电池甲", "color": Color(0.9, 0.2, 0.18)},
	{"kind": "battery", "id": "beta", "label": "电池乙", "color": Color(0.95, 0.75, 0.12)},
	{"kind": "battery", "id": "gamma", "label": "电池丙", "color": Color(0.18, 0.48, 0.95)},
	{"kind": "sample", "id": "a", "label": "样本甲", "color": Color(0.22, 0.86, 0.78)},
	{"kind": "sample", "id": "b", "label": "样本乙", "color": Color(0.9, 0.32, 0.64)},
	{"kind": "sample", "id": "c", "label": "样本丙", "color": Color(0.48, 0.9, 0.28)},
	{"kind": "treatment", "id": "dry", "label": "干燥剂", "color": Color(0.82, 0.88, 0.9)},
	{"kind": "treatment", "id": "wet", "label": "导湿垫", "color": Color(0.12, 0.58, 1.0)},
	{"kind": "treatment", "id": "heated", "label": "加热线圈", "color": Color(1.0, 0.3, 0.08)},
	{"kind": "connector", "id": "bar", "label": "金属棒", "color": Color(0.48, 0.55, 0.68)},
]

@onready var manager: Node = $Manager
@onready var task_card: Node = $TaskCard/ReadableComponent
@onready var status_panel: Label3D = $StatusPanel
@onready var history_panel: Label3D = $HistoryPanel
@onready var experiment_lamp: MeshInstance3D = $ExperimentLamp
@onready var treatment_effect: OmniLight3D = $TreatmentEffect
@onready var hud_rules: RichTextLabel = $ExperimentHUD/Layout/RulesPanel/Margin/Content/Rules
@onready var hud_state: Label = $ExperimentHUD/Layout/StatePanel/Margin/Content/State
@onready var hud_history: RichTextLabel = $ExperimentHUD/Layout/StatePanel/Margin/Content/History

var _lamp_material := StandardMaterial3D.new()


func _ready() -> void:
	_connect_button("ResetSetup", _reset_assembly)
	for slot: Node in $AssemblySlots.get_children():
		slot.component_changed.connect(_on_component_changed)
	manager.public_state_changed.connect(_refresh_display)
	manager.round_finished.connect(_on_round_finished)
	_lamp_material.albedo_color = Color(0.08, 0.09, 0.1)
	_lamp_material.emission_enabled = true
	experiment_lamp.material_override = _lamp_material
	task_card.readable_title = "实验任务说明"
	task_card.readable_content = manager.task_card_text()
	task_card.label_title.text = task_card.readable_title
	task_card.label_content.text = task_card.readable_content
	hud_rules.text = manager.task_card_text()
	_spawn_candidates(manager.round_seed)
	_refresh_display()


func _connect_button(button_name: String, callback: Callable) -> void:
	var button := get_node("Controls/%s" % button_name)
	button.pressed.connect(callback)


func _spawn_candidates(seed_value: int) -> void:
	for child: Node in $Candidates.get_children():
		child.queue_free()
	var anchors := $SearchAnchors.get_children()
	var rng := RandomNumberGenerator.new()
	rng.seed = seed_value ^ 0x4C4142
	for index: int in range(anchors.size() - 1, 0, -1):
		var swap_index := rng.randi_range(0, index)
		var anchor: Node = anchors[index]
		anchors[index] = anchors[swap_index]
		anchors[swap_index] = anchor
	for index: int in COMPONENT_SPECS.size():
		var spec: Dictionary = COMPONENT_SPECS[index]
		var component: Node3D = ComponentScene.instantiate()
		component.name = "%s_%s" % [spec.kind.capitalize(), spec.id.capitalize()]
		component.configure(spec.kind, spec.id, spec.label, spec.color)
		$Candidates.add_child(component)
		component.global_transform = anchors[index].global_transform
		component.rotate_y(rng.randf_range(-PI, PI))
		component.remember_home()


func _on_component_changed(kind: String, component_id: String) -> void:
	match kind:
		"battery":
			manager.select_battery(component_id)
		"sample":
			manager.select_sample(component_id)
		"treatment":
			manager.select_treatment(component_id)
		"connector":
			manager.set_metal_bar_installed(component_id == "bar")
	if manager.ai_play_public_state().setup_ready:
		manager.call_deferred("run_experiment")


func _reset_assembly() -> void:
	if not manager.is_setup_editable():
		return
	for slot: Node in $AssemblySlots.get_children():
		slot.eject_component()
	manager.reset_setup()


func _refresh_display() -> void:
	var public_state: Dictionary = manager.ai_play_public_state()
	status_panel.text = (
		"组装四种材料后自动分析\n实验：%s\n环境：%s　次数：%d / %d\n"
		+ "电池：%s　样本：%s　处理：%s\n金属棒：%s　状态：%s"
	) % [
		_display_zh(str(public_state.protocol)),
		_display_zh(str(public_state.environment)),
		public_state.attempts_used,
		public_state.attempts_limit,
		_display_zh(str(public_state.battery_installed)),
		_display_zh(str(public_state.selected_sample)),
		_display_zh(str(public_state.sample_state)),
		"已安装" if public_state.metal_bar_installed else "未安装",
		_status_zh(manager.status_code),
	]
	history_panel.text = _history_text()
	hud_state.text = _hud_state_text(public_state)
	hud_history.text = _hud_history_text()
	_update_lamp(str(public_state.last_lamp))
	_update_treatment_effect(str(public_state.sample_state))


func _history_text() -> String:
	if manager.result_history.is_empty():
		return "实验记录\n尚未运行实验"
	var lines: Array[String] = ["实验记录"]
	for index: int in manager.result_history.size():
		var result: Dictionary = manager.result_history[index]
		lines.append(
			"第%d次　电源%s　电流%s\n%s　温度%s　灯光%s" % [
				index + 1,
				_display_zh(str(result.power)),
				_display_zh(str(result.current)),
				_display_zh(str(result.stability)),
				_display_zh(str(result.temperature)),
				_display_zh(str(result.lamp)),
			]
		)
	return "\n".join(lines)


func _hud_state_text(public_state: Dictionary) -> String:
	return (
		"当前配置\n电池：%s    样本：%s\n处理：%s    金属棒：%s\n"
		+ "实验次数：%d / %d\n状态：%s"
	) % [
		_display_zh(str(public_state.battery_installed)),
		_display_zh(str(public_state.selected_sample)),
		_display_zh(str(public_state.sample_state)),
		"已安装" if public_state.metal_bar_installed else "未安装",
		public_state.attempts_used,
		public_state.attempts_limit,
		_status_zh(manager.status_code),
	]


func _hud_history_text() -> String:
	if manager.result_history.is_empty():
		return "实验记录\n尚未运行实验"
	var lines: Array[String] = ["实验记录"]
	for index: int in manager.result_history.size():
		var result: Dictionary = manager.result_history[index]
		lines.append(
			"第 %d 次：电源%s｜电流%s｜%s\n温度%s｜灯光%s" % [
				index + 1,
				_display_zh(str(result.power)),
				_display_zh(str(result.current)),
				_display_zh(str(result.stability)),
				_display_zh(str(result.temperature)),
				_display_zh(str(result.lamp)),
			]
		)
	return "\n\n".join(lines)


func _display_zh(value: String) -> String:
	return {
		"none": "未选择",
		"alpha": "甲",
		"beta": "乙",
		"gamma": "丙",
		"a": "甲",
		"b": "乙",
		"c": "丙",
		"stable_conduction": "稳定导电实验",
		"moisture_safety": "湿润安全实验",
		"thermal_tolerance": "耐热实验",
		"standard": "标准环境",
		"high_humidity": "高湿环境",
		"limited_cooling": "散热受限",
		"power_fluctuation": "电源波动",
		"dry": "干燥",
		"wet": "湿润",
		"heated": "加热",
		"low": "偏低",
		"normal": "正常",
		"high": "过高",
		"zero": "无",
		"safe": "安全",
		"stable": "稳定",
		"flicker": "闪烁",
		"interrupted": "中断",
		"elevated": "升高",
		"dangerous": "危险",
		"off": "熄灭",
		"dim": "微亮",
	}.get(value, value)


func _status_zh(value: String) -> String:
	return {
		"ready": "等待配置",
		"setup_changed": "配置未完成",
		"setup_incomplete": "缺少必要配置",
		"experiment_running": "实验运行中",
		"resetting": "正在复位",
		"retry_ready": "可以再次实验",
		"experiment_completed": "实验成功",
		"experiment_attempts_exhausted": "实验失败，次数已用尽",
	}.get(value, value)


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
	treatment_effect.visible = treatment in ["wet", "heated"]
	treatment_effect.light_color = (
		Color(0.15, 0.55, 1.0) if treatment == "wet" else Color(1.0, 0.22, 0.05)
	)


func _on_round_finished(outcome: String, reason: String) -> void:
	status_panel.text += "\n结果：%s　%s" % [
		"成功" if outcome == "success" else "失败",
		_status_zh(reason),
	]
