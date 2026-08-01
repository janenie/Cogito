extends Node3D

const INGREDIENT_PREVIEW := preload("res://conveyor_profit/scenes/ingredient_preview.tscn")

@onready var ingredient_path: Path3D = $Architecture/Conveyor/IngredientPath
@onready var gameplay: Node = $Gameplay


func _ready() -> void:
	_build_closed_path()
	_place_slots()
	gameplay.initialize(
		ingredient_path,
		$Stations/Tray/SelectedVisuals,
		$Stations/Tray/TrayLabel,
		$HUD/TotalTimeLabel,
		$HUD/WindowLabel,
		$HUD/DishLabel,
		$HUD/ProfitLabel,
		$HUD/StatusLabel,
		$Stations/MakeButton,
		$Stations/UndoButton,
	)


func _build_closed_path() -> void:
	var loop_curve := Curve3D.new()
	loop_curve.bake_interval = 0.2
	for point: Vector3 in [
		Vector3(-4.5, 1.18, -3.5),
		Vector3(-4.5, 1.18, 3.5),
		Vector3(4.5, 1.18, 3.5),
		Vector3(4.5, 1.18, -3.5),
		Vector3(2.7, 1.18, -3.5),
		Vector3(2.7, 1.18, 1.7),
		Vector3(-2.7, 1.18, 1.7),
		Vector3(-2.7, 1.18, -3.5),
	]:
		loop_curve.add_point(point)
	loop_curve.closed = true
	ingredient_path.curve = loop_curve


func _place_slots() -> void:
	for index: int in range(16):
		var follower := PathFollow3D.new()
		follower.name = "Slot%02d" % [index + 1]
		follower.loop = true
		follower.rotation_mode = PathFollow3D.ROTATION_ORIENTED
		ingredient_path.add_child(follower)
		follower.progress_ratio = float(index) / 16.0

		var preview := INGREDIENT_PREVIEW.instantiate() as Node3D
		preview.name = "IngredientPreview"
		follower.add_child(preview)
