class_name LoopStaircaseInvestigationBoard
extends Control

signal candidate_changed(floor_number: int, marked: bool)

const FLOOR_MIN: int = 2
const FLOOR_MAX: int = 9
const ROUND_COUNT: int = 5

var selected_floor: int = FLOOR_MIN
var _snapshots: Dictionary = {}
var _candidate_marks: Dictionary = {}
var _clue_lines: Array[String] = []
var _row_labels: Dictionary = {}
var _cells: Dictionary = {}
var _clue_label: Label


func _ready() -> void:
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	mouse_filter = Control.MOUSE_FILTER_STOP
	_build_ui()
	_refresh_rows()
	_refresh_cells()


func record_snapshot(floor_number: int, round_index: int, image: Image) -> void:
	if floor_number < FLOOR_MIN or floor_number > FLOOR_MAX:
		return
	if round_index < 0 or round_index >= ROUND_COUNT or image == null or image.is_empty():
		return
	var copy := image.duplicate()
	copy.resize(192, 108, Image.INTERPOLATE_LANCZOS)
	_snapshots[Vector2i(floor_number, round_index)] = ImageTexture.create_from_image(copy)
	_refresh_cells()


func has_snapshot(floor_number: int, round_index: int) -> bool:
	return _snapshots.has(Vector2i(floor_number, round_index))


func get_snapshot_count(round_index: int) -> int:
	var count: int = 0
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		count += int(has_snapshot(floor_number, round_index))
	return count


func get_floor_row_count() -> int:
	return FLOOR_MAX - FLOOR_MIN + 1


func get_round_column_count() -> int:
	return ROUND_COUNT


func set_clue_lines(lines: Array[String]) -> void:
	_clue_lines = lines.duplicate()
	if _clue_label != null:
		_clue_label.text = "\n".join(_clue_lines)


func select_next_floor() -> void:
	selected_floor = FLOOR_MIN if selected_floor >= FLOOR_MAX else selected_floor + 1
	_refresh_rows()


func select_previous_floor() -> void:
	selected_floor = FLOOR_MAX if selected_floor <= FLOOR_MIN else selected_floor - 1
	_refresh_rows()


func toggle_candidate(floor_number: int = selected_floor) -> void:
	if floor_number < FLOOR_MIN or floor_number > FLOOR_MAX:
		return
	_candidate_marks[floor_number] = not _candidate_marks.get(floor_number, false)
	candidate_changed.emit(floor_number, _candidate_marks[floor_number])
	_refresh_rows()


func is_candidate_marked(floor_number: int) -> bool:
	return _candidate_marks.get(floor_number, false)


func _build_ui() -> void:
	var shade := ColorRect.new()
	shade.name = "Shade"
	shade.color = Color(0.025, 0.035, 0.05, 0.96)
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(shade)
	var panel := PanelContainer.new()
	panel.name = "BoardPanel"
	panel.set_anchors_preset(Control.PRESET_CENTER)
	panel.position = Vector2(65, 40)
	panel.size = Vector2(1150, 640)
	add_child(panel)
	var layout := VBoxContainer.new()
	layout.name = "Layout"
	panel.add_child(layout)
	var title := Label.new()
	title.text = "调查板 / INVESTIGATION BOARD"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.add_theme_font_size_override("font_size", 24)
	layout.add_child(title)
	_clue_label = Label.new()
	_clue_label.name = "VisibleClues"
	_clue_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_clue_label.custom_minimum_size = Vector2(0, 110)
	_clue_label.add_theme_font_size_override("font_size", 20)
	_clue_label.text = "\n".join(_clue_lines)
	layout.add_child(_clue_label)
	var grid := GridContainer.new()
	grid.name = "SnapshotGrid"
	grid.columns = ROUND_COUNT + 1
	layout.add_child(grid)
	var corner := Label.new()
	corner.text = "楼层"
	grid.add_child(corner)
	for round_index: int in range(ROUND_COUNT):
		var header := Label.new()
		header.text = "第%d轮" % (round_index + 1)
		header.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
		grid.add_child(header)
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		var row_label := Label.new()
		row_label.custom_minimum_size = Vector2(88, 42)
		_row_labels[floor_number] = row_label
		grid.add_child(row_label)
		for round_index: int in range(ROUND_COUNT):
			var cell := TextureRect.new()
			cell.custom_minimum_size = Vector2(192, 88)
			cell.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
			cell.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
			_cells[Vector2i(floor_number, round_index)] = cell
			grid.add_child(cell)
	var help := Label.new()
	help.text = "↑/↓ 选择楼层　Space 标记候选　Tab 返回房间"
	help.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	layout.add_child(help)


func _refresh_rows() -> void:
	for floor_number: int in range(FLOOR_MIN, FLOOR_MAX + 1):
		var label := _row_labels.get(floor_number) as Label
		if label == null:
			continue
		var selector: String = "▶ " if floor_number == selected_floor else "  "
		var mark: String = "●" if is_candidate_marked(floor_number) else "○"
		label.text = "%s%s %dF" % [selector, mark, floor_number]


func _refresh_cells() -> void:
	for key: Variant in _cells.keys():
		var cell := _cells[key] as TextureRect
		if cell != null:
			cell.texture = _snapshots.get(key)
