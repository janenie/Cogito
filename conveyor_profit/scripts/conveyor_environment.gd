extends Node3D

const INGREDIENT_PREVIEW := preload("res://conveyor_profit/scenes/ingredient_preview.tscn")

const INGREDIENTS: Array[Dictionary] = [
	{"id": "lettuce", "cost": 1, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/lettuce.glb"},
	{"id": "tomato", "cost": 1, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/tomato.glb"},
	{"id": "bread", "cost": 2, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/bread.glb"},
	{"id": "egg", "cost": 2, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/egg.glb"},
	{"id": "mushroom", "cost": 2, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/mushroom.glb"},
	{"id": "cheese", "cost": 3, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/cheese.glb"},
	{"id": "fish", "cost": 4, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/fish.glb"},
	{"id": "meat", "cost": 5, "scene": "res://conveyor_profit/assets/kenney_food_kit/models/meat.glb"},
]

@onready var ingredient_path: Path3D = $Architecture/Conveyor/IngredientPath


func _ready() -> void:
	_build_closed_path()
	_place_ingredients()


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


func _place_ingredients() -> void:
	for index: int in range(16):
		var definition: Dictionary = INGREDIENTS[index % INGREDIENTS.size()]
		var follower := PathFollow3D.new()
		follower.name = "Slot%02d_%s" % [index + 1, definition.id]
		follower.loop = true
		follower.rotation_mode = PathFollow3D.ROTATION_ORIENTED
		follower.set_meta("ingredient_id", definition.id)
		ingredient_path.add_child(follower)
		follower.progress_ratio = float(index) / 16.0

		var preview := INGREDIENT_PREVIEW.instantiate() as Node3D
		preview.name = "IngredientPreview"
		follower.add_child(preview)
		var label := preview.get_node("CostLabel") as Label3D
		label.text = "$%d  %s" % [definition.cost, String(definition.id).to_upper()]

		var food_scene := load(definition.scene) as PackedScene
		if food_scene != null:
			var food := food_scene.instantiate() as Node3D
			food.name = "FoodModel"
			food.position.y = 0.16
			food.scale = Vector3.ONE * 1.35
			preview.add_child(food)
