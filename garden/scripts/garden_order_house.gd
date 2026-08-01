@tool
class_name GardenOrderHouse
extends Node3D

const VALID_GARDEN_SIZES := [&"small", &"medium", &"large"]

@export_range(1, 10, 1) var house_number := 1:
	set(value):
		house_number = clampi(value, 1, 10)
		_refresh_visuals()

@export_enum("small", "medium", "large") var garden_size := "small":
	set(value):
		garden_size = value if StringName(value) in VALID_GARDEN_SIZES else "small"
		_refresh_visuals()

@export var accent_color := Color("d66d52"):
	set(value):
		accent_color = value
		_refresh_visuals()


func _ready() -> void:
	_refresh_visuals()


func get_garden_size() -> String:
	return garden_size


func _refresh_visuals() -> void:
	if not is_inside_tree():
		return
	var address_label := get_node_or_null("AddressLabel") as Label3D
	if address_label != null:
		address_label.text = str(house_number)
	var house_mesh := get_node_or_null("HouseBody/BodyMesh") as MeshInstance3D
	if house_mesh != null:
		var material := house_mesh.material_override as StandardMaterial3D
		if material != null:
			material.albedo_color = accent_color
	var garden_bed := get_node_or_null("Garden/SoilBed") as MeshInstance3D
	if garden_bed != null:
		garden_bed.scale.x = _garden_width_scale()
	var visible_plants := _visible_plant_count()
	var plants := get_node_or_null("Garden/Plants")
	if plants != null:
		for index in plants.get_child_count():
			plants.get_child(index).visible = index < visible_plants


func _garden_width_scale() -> float:
	match garden_size:
		"medium":
			return 0.85
		"large":
			return 1.05
		_:
			return 0.65


func _visible_plant_count() -> int:
	match garden_size:
		"medium":
			return 5
		"large":
			return 7
		_:
			return 3
