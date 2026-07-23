class_name AIPlayGameOverScreen
extends CanvasLayer

const OUTCOME_TEXT := {
	"success": "解谜成功",
	"failure": "解谜失败",
}
const REASON_TEXT := {
	"correct_password": "密码正确",
	"wrong_password": "密码错误",
	"max_requests": "已达到最大决策次数",
}

@onready var outcome_label: Label = $Screen/Center/Content/Margin/Labels/Outcome
@onready var reason_label: Label = $Screen/Center/Content/Margin/Labels/Reason

var _finished: bool = false


func show_result(outcome: String, reason: String) -> void:
	if _finished:
		return
	_finished = true
	outcome_label.text = OUTCOME_TEXT.get(outcome, "解谜失败")
	reason_label.text = REASON_TEXT.get(reason, "游戏已终止")
	outcome_label.modulate = (
		Color("74d69b") if outcome == "success" else Color("ff8a70")
	)
	visible = true
	Input.set_mouse_mode(Input.MOUSE_MODE_VISIBLE)
	get_tree().paused = true
