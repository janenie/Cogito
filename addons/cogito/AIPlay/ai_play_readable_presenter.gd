class_name AIPlayReadablePresenter
extends RefCounted


static func configure(
	readable: ReadableComponent,
	fit_without_scrolling: bool = false,
) -> void:
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
