class_name RecipeMenuPager
extends Node3D

const CATALOG := preload("res://conveyor_profit/scripts/recipe_catalog.gd")
const MARKET_ECONOMY := preload("res://conveyor_profit/scripts/market_economy.gd")
const RECIPES_PER_PAGE: int = 5
const DISPLAY_NAMES := {
	"garden_salad": "花园沙拉\nGARDEN SALAD",
	"avocado_salad": "牛油果沙拉\nAVOCADO SALAD",
	"carrot_sausage_soup": "胡萝卜香肠汤\nCARROT SAUSAGE SOUP",
	"pumpkin_sausage_soup": "南瓜香肠汤\nPUMPKIN SAUSAGE SOUP",
	"classic_burger": "经典汉堡\nCLASSIC BURGER",
	"avocado_burger": "牛油果汉堡\nAVOCADO BURGER",
	"broccoli_bacon_omelet": "西兰花培根蛋卷\nBROCCOLI BACON OMELET",
	"corn_bacon_omelet": "玉米培根蛋卷\nCORN BACON OMELET",
	"garden_fish_sandwich": "田园鱼肉三明治\nGARDEN FISH SANDWICH",
	"avocado_fish_sandwich": "牛油果鱼肉三明治\nAVOCADO FISH SANDWICH",
}
const TITLE_COLORS: Array[Color] = [
	Color(0.31, 0.62, 0.31),
	Color(0.35, 0.72, 0.45),
	Color(0.89, 0.58, 0.2),
	Color(0.78, 0.42, 0.16),
	Color(0.72, 0.25, 0.2),
	Color(0.58, 0.2, 0.18),
	Color(0.52, 0.34, 0.62),
	Color(0.64, 0.48, 0.16),
	Color(0.2, 0.48, 0.7),
	Color(0.16, 0.38, 0.62),
]

var current_page: int = 0
var _category_multipliers: Dictionary = {
	"salad": 1.0,
	"soup": 1.0,
	"burger": 1.0,
	"omelet": 1.0,
	"sandwich": 1.0,
}
var _economy_labels: Dictionary = {}


func _ready() -> void:
	_populate_page($Pages/Page1, 0)
	_populate_page($Pages/Page2, RECIPES_PER_PAGE)
	$PreviousButton.activated.connect(_on_page_action)
	$NextButton.activated.connect(_on_page_action)
	show_page(0)


func get_page_recipe_ids(page_index: int) -> Array[String]:
	var result: Array[String] = []
	var start := page_index * RECIPES_PER_PAGE
	if page_index < 0 or start >= CATALOG.RECIPES.size():
		return result
	for index: int in range(start, mini(start + RECIPES_PER_PAGE, CATALOG.RECIPES.size())):
		result.append(String(CATALOG.RECIPES[index]["id"]))
	return result


func show_page(page_index: int) -> void:
	current_page = clampi(page_index, 0, 1)
	$Pages/Page1.visible = current_page == 0
	$Pages/Page2.visible = current_page == 1
	$PageLabel.text = "PAGE %d / 2" % (current_page + 1)


func set_category_multipliers(values: Dictionary) -> void:
	_category_multipliers = values.duplicate()
	for recipe_id: String in _economy_labels:
		_update_economy_label(recipe_id)


func get_displayed_economy(recipe_id: String) -> Dictionary:
	var recipe: Dictionary = CATALOG.recipe_by_id(recipe_id)
	if recipe.is_empty():
		return {}
	var multiplier := float(_category_multipliers.get(String(recipe["category"]), 1.0))
	return {
		"sale": MARKET_ECONOMY.adjusted_sale_price(recipe_id, multiplier),
		"profit": MARKET_ECONOMY.adjusted_profit(recipe_id, multiplier),
	}


func _on_page_action(action: String) -> void:
	if action == "page_previous":
		show_page(current_page - 1)
	elif action == "page_next":
		show_page(current_page + 1)


func _populate_page(page: Node3D, recipe_offset: int) -> void:
	for card_index: int in page.get_child_count():
		var recipe: Dictionary = CATALOG.RECIPES[recipe_offset + card_index]
		_build_card(page.get_child(card_index) as Node3D, recipe, recipe_offset + card_index)


func _build_card(card: Node3D, recipe: Dictionary, color_index: int) -> void:
	var background := MeshInstance3D.new()
	background.name = "Background"
	var background_mesh := BoxMesh.new()
	background_mesh.size = Vector3(3.45, 1.55, 0.08)
	var paper := StandardMaterial3D.new()
	paper.albedo_color = Color(0.94, 0.89, 0.76)
	paper.roughness = 0.88
	background_mesh.material = paper
	background.mesh = background_mesh
	card.add_child(background)

	var title_bar := MeshInstance3D.new()
	title_bar.name = "TitleBar"
	title_bar.position = Vector3(0, 0.48, -0.06)
	var title_mesh := BoxMesh.new()
	title_mesh.size = Vector3(3.3, 0.55, 0.04)
	var title_material := StandardMaterial3D.new()
	title_material.albedo_color = TITLE_COLORS[color_index]
	title_material.roughness = 0.72
	title_mesh.material = title_material
	title_bar.mesh = title_mesh
	card.add_child(title_bar)

	var recipe_id := String(recipe["id"])
	_add_label(card, "Title", Vector3(0, 0.48, -0.09), String(DISPLAY_NAMES[recipe_id]), 26, 4)
	var ingredients: PackedStringArray = []
	var ingredient_cost := 0
	for ingredient_id: String in recipe["ingredients"]:
		ingredients.append(ingredient_id.to_upper())
		ingredient_cost += CATALOG.ingredient_cost(ingredient_id)
	var ingredient_text := " + ".join(ingredients)
	if ingredients.size() == 4:
		ingredient_text = "%s + %s\n%s + %s" % [
			ingredients[0], ingredients[1], ingredients[2], ingredients[3],
		]
	_add_label(card, "Ingredients", Vector3(0, -0.02, -0.09), ingredient_text, 25, 2)
	var economy_label := _add_label(
		card,
		"Economy",
		Vector3(0, -0.55, -0.09),
		"",
		22,
		2,
	)
	economy_label.set_meta("ingredient_cost", ingredient_cost)
	_economy_labels[recipe_id] = economy_label
	_update_economy_label(recipe_id)


func _update_economy_label(recipe_id: String) -> void:
	var label := _economy_labels.get(recipe_id) as Label3D
	if label == null:
		return
	var economy := get_displayed_economy(recipe_id)
	label.text = "COST $%d  ·  SALE $%d\nPROFIT +$%d" % [
		int(label.get_meta("ingredient_cost", 0)),
		int(economy.get("sale", 0)),
		int(economy.get("profit", 0)),
	]


func _add_label(
	card: Node3D,
	label_name: String,
	label_position: Vector3,
	label_text: String,
	font_size: int,
	outline_size: int,
) -> Label3D:
	var label := Label3D.new()
	label.name = label_name
	label.position = label_position
	label.rotation.y = PI
	label.text = label_text
	label.font_size = font_size
	label.outline_size = outline_size
	label.modulate = Color(0.08, 0.09, 0.075)
	card.add_child(label)
	return label
