extends SceneTree

const SCENE_PATH := "res://conveyor_profit/scenes/conveyor_profit_environment.tscn"

var failures: Array[String] = []


func _initialize() -> void:
	call_deferred("_run_test")


func _run_test() -> void:
	var pager_script: GDScript = load("res://conveyor_profit/scripts/recipe_menu_pager.gd")
	_check(pager_script != null, "recipe menu pager loads")
	if pager_script == null:
		quit(1)
		return
	var environment := (load(SCENE_PATH) as PackedScene).instantiate()
	root.add_child(environment)
	await process_frame
	var menu := environment.get_node("Stations/MenuBoard")
	_check(menu.get_script() == pager_script, "menu board uses the catalog-driven pager")
	_check(menu.get_page_recipe_ids(0) == [
		"garden_salad", "avocado_salad", "carrot_sausage_soup",
		"pumpkin_sausage_soup", "classic_burger",
	], "page one contains the first five stable recipes")
	_check(menu.get_page_recipe_ids(1) == [
		"avocado_burger", "broccoli_bacon_omelet", "corn_bacon_omelet",
		"garden_fish_sandwich", "avocado_fish_sandwich",
	], "page two contains the next five stable recipes")
	var page_one := menu.get_node("Pages/Page1") as Node3D
	var page_two := menu.get_node("Pages/Page2") as Node3D
	_check(page_one.get_child_count() == 5, "page one renders five cards")
	_check(page_two.get_child_count() == 5, "page two renders five cards")
	_check(page_one.visible and not page_two.visible, "menu starts on page one")
	_check(_page_text(page_one).contains("GARDEN SALAD"), "page one shows full recipe names")
	_check(_page_text(page_one).contains("LETTUCE + TOMATO + CARROT"), "page one shows full ingredients")
	_check(_page_text(page_one).contains("COST $3  ·  SALE $7"), "page one shows cost and sale")
	_check(_page_text(page_one).contains("PROFIT +$4"), "page one shows profit")
	menu.get_node("NextButton").activate()
	_check(not page_one.visible and page_two.visible, "next control switches to page two")
	_check(menu.get_node("PageLabel").text == "PAGE 2 / 2", "page indicator follows next control")
	_check(_page_text(page_two).contains("AVOCADO FISH SANDWICH"), "page two shows its final recipe")
	menu.get_node("PreviousButton").activate()
	_check(page_one.visible and not page_two.visible, "previous control returns to page one")
	environment.queue_free()
	quit(1 if not failures.is_empty() else 0)


func _page_text(page: Node) -> String:
	var result := ""
	for card: Node in page.get_children():
		for label_name: String in ["Title", "Ingredients", "Economy"]:
			var label := card.get_node_or_null(label_name) as Label3D
			if label != null:
				result += label.text + "\n"
	return result


func _check(condition: bool, message: String) -> void:
	if not condition:
		failures.append(message)
		push_error(message)
