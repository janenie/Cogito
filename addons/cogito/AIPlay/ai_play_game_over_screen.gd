class_name AIPlayGameOverScreen
extends CanvasLayer

const OUTCOME_TEXT := {
	"correct_password": "解谜成功",
	"wrong_password": "解谜失败",
	"max_requests": "解谜失败",
	"key_picked_up": "任务成功",
	"books_in_ceo_office": "任务成功",
	"wrong_book_pickup": "任务失败",
	"meeting_door_closed": "任务成功",
	"cleanup_complete": "任务成功",
	"cleanup_incomplete": "任务失败",
	"garden_tasks_complete": "任务成功",
	"garden_task_failed": "任务失败",
	"circuit_repaired": "任务成功",
	"wrong_breaker": "任务失败",
	"incorrect_circuit_configuration": "任务失败",
	"meeting_prepared": "任务成功",
	"incorrect_seating_assignment": "任务失败",
	"experiment_completed": "实验成功",
	"experiment_attempts_exhausted": "实验失败",
	"efficiency_target_reached": "经营成功",
	"efficiency_below_target": "经营失败",
	"correct_floor_selected": "任务成功",
	"wrong_floor_selected": "任务失败",
}
const REASON_TEXT := {
	"correct_password": "密码正确",
	"wrong_password": "密码错误",
	"max_requests": "达到最大步长",
	"key_picked_up": "已找到办公室钥匙",
	"books_in_ceo_office": "三本任务书已按顺序送达 CEO OFFICE",
	"wrong_book_pickup": "拿取了错误的书或搬运顺序不正确",
	"meeting_door_closed": "已打招呼并关上会议室门",
	"cleanup_complete": "所有垃圾已清理",
	"cleanup_incomplete": "还有垃圾没有处理",
	"garden_tasks_complete": "浇水和下雨警报都已完成",
	"garden_task_failed": "花园任务未完成",
	"circuit_repaired": "照明电路已修复",
	"wrong_breaker": "断路器选择错误",
	"incorrect_circuit_configuration": "照明配置不正确",
	"meeting_prepared": "会议资料已正确分发",
	"incorrect_seating_assignment": "会议资料席位不正确",
	"experiment_completed": "已组装出符合目标的实验回路",
	"experiment_attempts_exhausted": "三次实验机会已用完",
	"efficiency_target_reached": "传送带经营效率达到目标",
	"efficiency_below_target": "传送带经营效率未达到目标",
	"correct_floor_selected": "已找到真正的出口楼层",
	"wrong_floor_selected": "选择了错误的出口楼层",
}

@onready var outcome_label: Label = $Screen/Center/Content/Margin/Labels/Outcome
@onready var reason_label: Label = $Screen/Center/Content/Margin/Labels/Reason
@onready var exit_button: Button = $Screen/Center/Content/Margin/Labels/ExitButton

var _finished: bool = false


func _ready() -> void:
	exit_button.pressed.connect(_request_exit)


func _input(event: InputEvent) -> void:
	if not _should_exit_for_event(event):
		return
	get_viewport().set_input_as_handled()
	_request_exit()


func show_result(outcome: String, reason: String) -> void:
	if _finished:
		return
	_finished = true
	outcome_label.text = OUTCOME_TEXT.get(reason, "游戏结束")
	reason_label.text = REASON_TEXT.get(reason, "游戏已终止")
	outcome_label.modulate = (
		Color("74d69b") if outcome == "success" else Color("ff8a70")
	)
	visible = true
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	get_tree().paused = true
	exit_button.grab_focus()


func _should_exit_for_event(event: InputEvent) -> bool:
	if not _finished or event.device == AIPlayExecutor.SYNTHETIC_DEVICE_ID:
		return false
	if not event is InputEventKey:
		return false
	var key_event := event as InputEventKey
	return (
		key_event.pressed
		and not key_event.echo
		and (
			key_event.keycode == KEY_ESCAPE
			or key_event.physical_keycode == KEY_ESCAPE
		)
	)


func _request_exit() -> void:
	get_tree().quit()
