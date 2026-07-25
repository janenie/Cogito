class_name DailyRoutineManager
extends Node

signal objective_changed(text: String)
signal trash_count_changed(current: int, required: int)
signal routine_completed
signal routine_failed_changed(reason: String)
signal trash_bag_ready
signal trash_bag_taken
signal routine_retried
signal breakfast_completed
signal held_item_changed(label: String)

const STATE_START := "START"
const STATE_GET_MILK := "GET_MILK"
const STATE_EAT_BREAKFAST := "EAT_BREAKFAST"
const STATE_COLLECT_LOOSE_TRASH := "COLLECT_LOOSE_TRASH"
const STATE_EMPTY_ROOM_BINS := "EMPTY_ROOM_BINS"
const STATE_CLEAR_ROOM_BINS := STATE_EMPTY_ROOM_BINS
const STATE_PLACE_AT_DOOR := "PLACE_AT_DOOR"
const STATE_COMPLETE := "COMPLETE"
const STATE_FAILED := "FAILED"

@export var time_system_path: NodePath
@export var required_trash_count := 3
@export var loose_trash_min := 1
@export var loose_trash_max := 2
@export var required_trash_bag_count := 0
@export var clear_bag_distance := 1.6

var time_system: Node
var current_state := STATE_START
var current_objective := ""
var collected_trash_count := 0
var disposed_trash_count := 0
var room_bin_counts: Dictionary = {}
var has_trash_bag := false
var held_bin_room := ""
var placed_trash_bag_count := 0
var has_milk := false
var milk_available := true
var milk_drunk := false
var breakfast_finished := false
var has_loose_trash := false
var held_trash_room := ""
var routine_complete := false
var routine_failed := false
var failure_reason := ""

func _ready() -> void:
	if time_system == null:
		time_system = get_node_or_null(time_system_path)
	_connect_time_system()
	start_routine()

func start_routine() -> void:
	current_state = STATE_START
	current_objective = "把全部垃圾扔进客厅垃圾桶。"
	collected_trash_count = 0
	disposed_trash_count = 0
	room_bin_counts = {
		"living_room": 0,
	}
	has_trash_bag = false
	held_bin_room = ""
	placed_trash_bag_count = 0
	has_milk = false
	milk_available = true
	milk_drunk = false
	breakfast_finished = false
	has_loose_trash = false
	held_trash_room = ""
	routine_complete = false
	routine_failed = false
	failure_reason = ""
	if time_system != null:
		time_system.paused = false
	objective_changed.emit(current_objective)
	trash_count_changed.emit(collected_trash_count, required_trash_count)
	_emit_held_item_changed()

func set_required_loose_trash_count(count: int) -> void:
	var loose_count := clampi(count, loose_trash_min, loose_trash_max)
	required_trash_count = loose_count + 1
	trash_count_changed.emit(collected_trash_count, required_trash_count)

func read_start_hint() -> void:
	if routine_complete or routine_failed:
		return
	if current_state == STATE_START:
		current_state = STATE_COLLECT_LOOSE_TRASH
	_set_objective("清理全部垃圾后，点击客厅垃圾桶旁边的完成按钮。")

func take_milk() -> bool:
	if routine_complete or routine_failed:
		return false
	if current_state == STATE_START:
		read_start_hint()
	if has_loose_trash or has_trash_bag:
		_set_objective("手上已经有东西了。")
		return false
	if has_milk:
		_set_objective("手上已经有东西了。")
		return false
	if milk_drunk:
		_set_objective("已经拿过了。")
		return false
	if not milk_available:
		_set_objective("这里没有。")
		return false
	has_loose_trash = true
	held_trash_room = "expired_milk"
	milk_available = false
	milk_drunk = true
	breakfast_finished = true
	if current_state == STATE_START:
		current_state = STATE_COLLECT_LOOSE_TRASH
	_set_objective("拿到了过期牛奶。")
	_emit_held_item_changed()
	return true

func place_milk_down() -> bool:
	if routine_complete or routine_failed:
		return false
	if not has_milk:
		_set_objective("没有可以放下的牛奶。")
		return false
	has_milk = false
	milk_available = true
	_set_objective("已放下。")
	_emit_held_item_changed()
	return true

func drink_milk() -> bool:
	if routine_complete or routine_failed:
		return false
	if breakfast_finished or milk_drunk:
		_set_objective("牛奶已经过期了。")
		return false
	if not has_milk and not milk_available:
		_set_objective("没有可以使用的牛奶。")
		return false
	has_milk = false
	milk_available = false
	milk_drunk = true
	breakfast_finished = true
	has_loose_trash = true
	held_trash_room = "milk_carton"
	if current_state == STATE_START:
		current_state = STATE_COLLECT_LOOSE_TRASH
	_set_objective("空牛奶盒。把它扔进客厅垃圾桶。")
	_emit_held_item_changed()
	breakfast_completed.emit()
	return true

func eat_breakfast() -> bool:
	return drink_milk()

func collect_loose_trash() -> void:
	pick_up_loose_trash("kitchen")

func pick_up_loose_trash(room_id: String) -> bool:
	if routine_complete or routine_failed:
		return false
	if current_state == STATE_START:
		read_start_hint()
	if has_loose_trash or has_milk or has_trash_bag:
		_set_objective("手上只能拿一个物品。")
		return false
	if current_state != STATE_COLLECT_LOOSE_TRASH and current_state != STATE_GET_MILK and current_state != STATE_EAT_BREAKFAST:
		_set_objective("已经整理过了。")
		return false
	has_loose_trash = true
	held_trash_room = room_id
	_set_objective("拿到垃圾了，把它扔进客厅垃圾桶。")
	_emit_held_item_changed()
	return true

func deposit_held_trash(room_id: String) -> bool:
	if routine_complete or routine_failed:
		return false
	if not has_loose_trash:
		_set_objective("手上没有垃圾。")
		return false
	has_loose_trash = false
	held_trash_room = ""
	room_bin_counts[room_id] = int(room_bin_counts.get(room_id, 0)) + 1
	collected_trash_count = mini(required_trash_count, collected_trash_count + 1)
	disposed_trash_count = collected_trash_count
	trash_count_changed.emit(collected_trash_count, required_trash_count)
	_emit_held_item_changed()
	if _ready_to_complete():
		_set_objective("垃圾清理完了，点击垃圾桶旁边的完成按钮。")
	else:
		_set_objective("继续清理其它垃圾。")
	return true

func submit_cleanup() -> bool:
	if routine_complete or routine_failed:
		return false
	if _ready_to_complete():
		_complete_routine()
		return true
	fail_routine("任务失败：还有垃圾没有扔进客厅垃圾桶。")
	return false

func place_trash_at_door() -> bool:
	_set_objective("Use the living room trash bin.")
	return false

func take_room_bin(room_id: String, actor: Node3D = null, bin_position := Vector3.ZERO) -> bool:
	_set_objective("No need to pick up the trash bin.")
	return false

func clear_room_bin(room_id: String, actor: Node3D = null, bin_position := Vector3.ZERO) -> bool:
	return take_room_bin(room_id, actor, bin_position)

func take_trash_bag() -> bool:
	return take_room_bin("living_room")

func place_trash_bag_at_door() -> bool:
	return empty_held_bin_at_door()

func empty_held_bin_at_door() -> bool:
	_set_objective("There is no front-door pickup today.")
	return false

func evaluate_deadline() -> void:
	return

func fail_routine(reason: String) -> void:
	if routine_complete or routine_failed:
		return
	routine_failed = true
	current_state = STATE_FAILED
	failure_reason = reason
	if time_system != null:
		time_system.paused = true
	_set_objective(reason)
	routine_failed_changed.emit(reason)

func retry_routine() -> void:
	if time_system != null:
		time_system.reset_clock()
	start_routine()
	routine_retried.emit()

func held_item_label() -> String:
	if has_milk:
		return "牛奶"
	if has_loose_trash:
		if held_trash_room == "expired_milk":
			return "过期牛奶"
		return "垃圾"
	if has_trash_bag:
		return "垃圾桶"
	return "空"

func refresh_warning_objective() -> void:
	return

func _connect_time_system() -> void:
	if time_system == null:
		return
	if not time_system.deadline_reached.is_connected(_on_deadline_reached):
		time_system.deadline_reached.connect(_on_deadline_reached)
	if not time_system.time_changed.is_connected(_on_time_changed):
		time_system.time_changed.connect(_on_time_changed)

func _on_deadline_reached(deadline_id: String) -> void:
	if deadline_id == "trash_pickup":
		evaluate_deadline()

func _on_time_changed(_formatted: String, _minutes: float) -> void:
	refresh_warning_objective()

func _set_objective(text: String) -> void:
	current_objective = text
	objective_changed.emit(current_objective)

func _emit_held_item_changed() -> void:
	held_item_changed.emit(held_item_label())

func _complete_routine() -> void:
	routine_complete = true
	current_state = STATE_COMPLETE
	if time_system != null:
		time_system.paused = true
	_set_objective("任务成功：所有垃圾都已经扔进客厅垃圾桶。")
	routine_completed.emit()

func _ready_to_complete() -> bool:
	return milk_drunk and collected_trash_count >= required_trash_count

func _filled_bin_count() -> int:
	var count := 0
	for room_id in room_bin_counts:
		if int(room_bin_counts.get(room_id, 0)) > 0:
			count += 1
	return count

func _room_label(room_id: String) -> String:
	match room_id:
		"kitchen":
			return "kitchen"
		"living_room":
			return "living room"
		"bedroom":
			return "bedroom"
		_:
			return room_id

func _actor_position(actor: Node3D) -> Vector3:
	if actor.is_inside_tree():
		return actor.global_position
	return actor.position
