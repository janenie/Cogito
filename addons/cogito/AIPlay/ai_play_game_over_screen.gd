class_name AIPlayGameOverScreen
extends CanvasLayer

const OUTCOME_TEXT := {
	"correct_password": "解谜成功",
	"wrong_password": "解谜失败",
	"max_requests": "解谜失败",
	"key_picked_up": "任务成功",
	"book_in_box": "任务成功",
	"meeting_door_closed": "任务成功",
}
const REASON_TEXT := {
	"correct_password": "密码正确",
	"wrong_password": "密码错误",
	"max_requests": "达到最大步长",
	"key_picked_up": "已找到办公室钥匙",
	"book_in_box": "已整理档案室书籍",
	"meeting_door_closed": "已打招呼并关上会议室门",
}

@onready var outcome_label: Label = $Screen/Center/Content/Margin/Labels/Outcome
@onready var reason_label: Label = $Screen/Center/Content/Margin/Labels/Reason

var _finished: bool = false


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
