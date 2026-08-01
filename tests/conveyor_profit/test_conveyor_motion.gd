extends SceneTree

var failures: Array[String] = []


func _initialize() -> void:
	var motion: GDScript = load("res://conveyor_profit/scripts/conveyor_motion.gd")
	_check(is_equal_approx(motion.advance(2.0, 1.5, 2.0, 10.0), 5.0), "advances")
	_check(is_equal_approx(motion.advance(9.0, 2.0, 1.0, 10.0), 1.0), "wraps forward")
	_check(is_equal_approx(motion.advance(0.5, -1.0, 1.0, 10.0), 9.5), "wraps reverse")
	_check(is_equal_approx(motion.advance(4.0, 3.0, 0.0, 10.0), 4.0), "zero delta")
	quit(1 if not failures.is_empty() else 0)


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
