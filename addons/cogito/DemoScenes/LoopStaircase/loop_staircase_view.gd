class_name LoopStaircaseView
extends Control


func _draw() -> void:
	var center_x: float = size.x * 0.52
	var base_y: float = size.y * 0.82
	var level_gap: float = max(size.y * 0.16, 72.0)
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.03, 0.12, 0.2, 0.72), true)
	draw_line(Vector2(center_x, size.y * 0.08), Vector2(center_x, size.y * 0.92), Color(0.88, 0.55, 0.24), 22.0)
	for index: int in range(5):
		var y: float = base_y - level_gap * index
		draw_arc(Vector2(center_x, y), size.x * 0.24, PI * 0.05, PI * 1.12, 48, Color(0.96, 0.95, 0.9), 12.0)
		draw_line(Vector2(center_x - 170, y), Vector2(center_x + 220, y), Color(0.95, 0.9, 0.82), 18.0)
		for step: int in range(8):
			var angle: float = PI * (0.15 + step * 0.12)
			var inner := Vector2(center_x + cos(angle) * 52.0, y - sin(angle) * 52.0)
			var outer := Vector2(center_x + cos(angle) * 168.0, y - sin(angle) * 72.0)
			draw_line(inner, outer, Color(0.82, 0.86, 0.88), 6.0)
