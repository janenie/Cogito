class_name AIPlayReadablePresenter
extends RefCounted

const TASK_MARKER_SCALE := 1.75
const CLUE_MARKER_SCALE := 1.4
const BASE_VISUAL_SCALE_META := &"ai_play_base_visual_scale"


static func configure(
	readable: ReadableComponent,
	fit_without_scrolling: bool = false,
) -> void:
	_configure_marker_visuals(
		readable,
		TASK_MARKER_SCALE if fit_without_scrolling else CLUE_MARKER_SCALE,
	)
	var readable_ui := readable.get_node_or_null("ReadableUi") as Control
	var scroll := readable.get_node_or_null(
		"ReadableUi/Bindings/ScrollContainer"
	) as ScrollContainer
	var title := readable.get_node_or_null(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableTitle"
	) as Label
	var content := readable.get_node_or_null(
		"ReadableUi/Bindings/ScrollContainer/VBoxContainer/ReadableContent"
	) as RichTextLabel
	var popup_half_width: float = 500.0 if fit_without_scrolling else 440.0
	var popup_half_height: float = 430.0 if fit_without_scrolling else 360.0
	var text_width: float = 900.0 if fit_without_scrolling else 760.0
	if readable_ui != null:
		readable_ui.offset_left = -popup_half_width
		readable_ui.offset_top = -popup_half_height
		readable_ui.offset_right = popup_half_width
		readable_ui.offset_bottom = popup_half_height
	if scroll != null:
		scroll.custom_minimum_size = Vector2(text_width, 0.0)
		if fit_without_scrolling:
			scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
			scroll.follow_focus = false
	if title != null:
		title.custom_minimum_size = Vector2(text_width, 0.0)
		title.add_theme_font_size_override("font_size", 42)
	if content != null:
		content.custom_minimum_size = Vector2(text_width, 0.0)
		content.add_theme_font_size_override("normal_font_size", 24)


static func _configure_marker_visuals(
	readable: ReadableComponent,
	multiplier: float,
) -> void:
	var marker_root := readable.get_parent_node_3d()
	if marker_root == null:
		return
	for child: Node in marker_root.get_children():
		if not _is_hint_marker_visual(child):
			continue
		var visual := child as Node3D
		if not visual.has_meta(BASE_VISUAL_SCALE_META):
			visual.set_meta(BASE_VISUAL_SCALE_META, visual.scale)
		var base_scale: Vector3 = visual.get_meta(
			BASE_VISUAL_SCALE_META,
			visual.scale,
		)
		visual.scale = base_scale * multiplier


static func _is_hint_marker_visual(node: Node) -> bool:
	if node is Sprite3D:
		return true
	return (
		node is MeshInstance3D
		and String(node.name) in ["Center", "Stick"]
	)
