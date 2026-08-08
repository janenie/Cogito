class_name LaboratoryExperimentManager
extends Node

const Cases = preload("res://addons/cogito/DemoScenes/Laboratory/laboratory_experiment_cases.gd")
const ROUND_SEED_PARSER = preload(
	"res://addons/cogito/AIPlay/ai_play_round_seed.gd"
)

signal round_finished(outcome: String, reason: String)
signal public_state_changed()

enum State {
	READY,
	RUNNING,
	RESETTING,
	FINISHED,
}

const ATTEMPTS_LIMIT := 3
const BATTERY_LABELS: Array[String] = ["alpha", "beta", "gamma"]
const SAMPLE_LABELS: Array[String] = ["a", "b", "c"]
const TREATMENTS: Array[String] = ["dry", "wet", "heated"]
const OBJECTIVES := {
	"stable_conduction": "让回路保持安全稳定，并使实验灯持续点亮。",
	"moisture_safety": "完成湿润测试，使电流安全且实验灯稳定点亮。",
	"thermal_tolerance": "完成加热测试，同时避免危险温度和回路不稳定。",
}
const PROTOCOL_NAMES_ZH := {
	"stable_conduction": "稳定导电实验",
	"moisture_safety": "湿润安全实验",
	"thermal_tolerance": "耐热实验",
}
const OBJECTIVES_ZH := {
	"stable_conduction": "让回路保持安全稳定，并使实验灯持续点亮。",
	"moisture_safety": "完成湿润测试，使电流安全且实验灯稳定点亮。",
	"thermal_tolerance": "完成加热测试，同时避免危险温度和回路不稳定。",
}
const ENVIRONMENT_NAMES_ZH := {
	"standard": "标准环境",
	"high_humidity": "高湿环境",
	"limited_cooling": "散热受限",
	"power_fluctuation": "电源波动",
}

@export_range(0.0, 10.0, 0.1) var stability_seconds := 3.0
@export var initial_seed := -1

var state := State.READY
var round_data: Dictionary = {}
var round_seed := 0
var attempts_used := 0
var battery_installed := "none"
var selected_sample := "none"
var sample_state := "dry"
var metal_bar_installed := false
var last_result: Dictionary = {}
var result_history: Array[Dictionary] = []
var completed := false
var failed := false
var status_code := "ready"

var _round_generation := 0


func _ready() -> void:
	var seed_value := initial_seed
	var requested_seed: Dictionary = ROUND_SEED_PARSER.parse(
		OS.get_cmdline_user_args()
	)
	if not requested_seed["valid"]:
		push_error("Invalid --ai-play-round-seed argument")
	elif requested_seed["provided"]:
		seed_value = ROUND_SEED_PARSER.runtime_seed(
			int(requested_seed["value"])
		)
	if seed_value < 0:
		seed_value = int(Time.get_unix_time_from_system())
	start_round(seed_value)


func start_round(seed_value: int) -> void:
	_round_generation += 1
	round_seed = seed_value
	round_data = Cases.build_round(seed_value)
	state = State.READY
	attempts_used = 0
	battery_installed = "none"
	selected_sample = "none"
	sample_state = "none"
	metal_bar_installed = false
	last_result = {}
	result_history.clear()
	completed = false
	failed = false
	status_code = "ready"
	public_state_changed.emit()


func select_battery(label: String) -> void:
	if state != State.READY or label not in BATTERY_LABELS + ["none"]:
		return
	battery_installed = label
	status_code = "setup_changed"
	public_state_changed.emit()


func select_sample(label: String) -> void:
	if state != State.READY or label not in SAMPLE_LABELS + ["none"]:
		return
	selected_sample = label
	status_code = "setup_changed"
	public_state_changed.emit()


func select_treatment(treatment: String) -> void:
	if state != State.READY or treatment not in TREATMENTS + ["none"]:
		return
	sample_state = treatment
	status_code = "setup_changed"
	public_state_changed.emit()


func set_metal_bar_installed(installed: bool) -> void:
	if state != State.READY:
		return
	metal_bar_installed = installed
	status_code = "setup_changed"
	public_state_changed.emit()


func run_experiment() -> void:
	if state != State.READY:
		return
	if not _setup_ready():
		status_code = "setup_incomplete"
		public_state_changed.emit()
		return

	attempts_used += 1
	state = State.RUNNING
	status_code = "experiment_running"
	last_result = Cases.evaluate(
		round_data,
		battery_installed,
		selected_sample,
		sample_state,
	)
	result_history.append(last_result.duplicate(true))
	if result_history.size() > ATTEMPTS_LIMIT:
		result_history.pop_front()
	public_state_changed.emit()

	if last_result.get("success", false):
		var generation := _round_generation
		await get_tree().create_timer(stability_seconds).timeout
		if generation == _round_generation and state == State.RUNNING:
			_finish("success", "experiment_completed")
	elif attempts_used >= ATTEMPTS_LIMIT:
		_finish("failure", "experiment_attempts_exhausted")
	else:
		_reset_after_failed_experiment()


func reset_setup() -> void:
	if state != State.READY:
		return
	battery_installed = "none"
	selected_sample = "none"
	sample_state = "none"
	metal_bar_installed = false
	status_code = "ready"
	public_state_changed.emit()


func is_setup_editable() -> bool:
	return state == State.READY


func ai_play_public_state() -> Dictionary:
	return {
		"objective": OBJECTIVES.get(round_data.get("protocol", ""), "安全完成实验。"),
		"protocol": round_data.get("protocol", "stable_conduction"),
		"environment": round_data.get("environment", "standard"),
		"attempts_used": attempts_used,
		"attempts_limit": ATTEMPTS_LIMIT,
		"battery_installed": battery_installed,
		"selected_sample": selected_sample,
		"sample_state": sample_state,
		"metal_bar_installed": metal_bar_installed,
		"setup_ready": _setup_ready(),
		"experiment_running": state == State.RUNNING,
		"last_power": last_result.get("power", "none"),
		"last_current": last_result.get("current", "none"),
		"last_stability": last_result.get("stability", "none"),
		"last_temperature": last_result.get("temperature", "none"),
		"last_lamp": last_result.get("lamp", "none"),
		"completed": completed,
		"failed": failed,
	}


func task_card_text() -> String:
	return (
		"实验 / EXPERIMENT：%s\n目标 / OBJECTIVE：%s\n环境 / ENVIRONMENT：%s\n\n"
		+ "游戏规则 / RULES\n"
		+ "1. 在附近两个实验区域寻找电池、样本、处理模块和金属棒。\n"
		+ "2. 对准材料按一下 E 拿取（无需按住），带回起点放入对应插槽。\n"
		+ "3. 把四种材料带回起点插槽，组装完整后会自动分析。\n"
		+ "4. 只有完整配置的自动分析才消耗机会，最多 3 次。\n"
		+ "5. 根据电流、稳定性、温度和灯光结果更换单个组件。\n\n"
		+ "本局已知条件 / CLUES\n• %s\n• %s"
	) % [
		PROTOCOL_NAMES_ZH.get(round_data.get("protocol", ""), "实验协议"),
		OBJECTIVES_ZH.get(round_data.get("protocol", ""), "安全完成实验。"),
		ENVIRONMENT_NAMES_ZH.get(round_data.get("environment", ""), "标准环境"),
		round_data.get("clues_zh", ["", ""])[0],
		round_data.get("clues_zh", ["", ""])[1],
	]


func _setup_ready() -> bool:
	return (
		battery_installed in BATTERY_LABELS
		and selected_sample in SAMPLE_LABELS
		and sample_state in TREATMENTS
		and metal_bar_installed
	)


func _reset_after_failed_experiment() -> void:
	state = State.RESETTING
	status_code = "resetting"
	public_state_changed.emit()
	state = State.READY
	status_code = "retry_ready"
	public_state_changed.emit()


func _finish(outcome: String, reason: String) -> void:
	if state == State.FINISHED:
		return
	state = State.FINISHED
	completed = outcome == "success"
	failed = outcome == "failure"
	status_code = reason
	public_state_changed.emit()
	round_finished.emit(outcome, reason)
