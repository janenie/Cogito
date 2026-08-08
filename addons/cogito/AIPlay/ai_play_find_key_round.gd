class_name AIPlayFindKeyRound
extends RefCounted

const PACK_IDS: Array[String] = ["POLARIS", "ATLAS", "ORBIT", "NOVA"]
const PACKS := {
	"POLARIS": {
		"contract": "Polaris",
		"scope": "董事会档案数字化及审批流部署",
		"value": "¥480,000（含税）",
		"rooms": ["MEETING_ROOM", "UPPER_OFFICE_CEO", "CUBICLE_AREA"],
		"handlers": ["李明", "王芳", "陈宇"],
	},
	"ATLAS": {
		"contract": "Atlas",
		"scope": "跨部门合同台账与归档系统实施",
		"value": "¥520,000（含税）",
		"rooms": ["UPPER_OFFICE_CEO", "MEETING_ROOM", "CUBICLE_AREA"],
		"handlers": ["陈宇", "李明", "王芳"],
	},
	"ORBIT": {
		"contract": "Orbit",
		"scope": "区域办公室文件流转与权限审计升级",
		"value": "¥465,000（含税）",
		"rooms": ["CUBICLE_AREA", "MEETING_ROOM", "UPPER_OFFICE_CEO"],
		"handlers": ["王芳", "陈宇", "李明"],
	},
	"NOVA": {
		"contract": "Nova",
		"scope": "保密档案检索与会议材料追踪平台部署",
		"value": "¥510,000（含税）",
		"rooms": ["CUBICLE_AREA", "UPPER_OFFICE_CEO", "MEETING_ROOM"],
		"handlers": ["李明", "王芳", "陈宇"],
	},
}
const VERSIONS: Array[String] = ["v0.1", "v0.8", "v1.0"]
const VERSION_LABELS: Array[String] = [
	"INITIAL DRAFT v0.1",
	"REVIEW REVISION v0.8",
	"FINAL v1.0",
]
const STATUSES: Array[String] = [
	"INITIAL DRAFT",
	"UNDER REVIEW",
	"PREPARED FOR SUBMISSION",
]
const DAY_SECONDS := 86_400
const DATE_WINDOW_DAY_COUNT := 228
const FIXED_BASE_DAY := {
	"year": 2026,
	"month": 1,
	"day": 15,
	"hour": 0,
	"minute": 0,
	"second": 0,
}


static func build(round_seed: int) -> Dictionary:
	assert(round_seed >= 0)
	var pack_order: Array[String] = PACK_IDS.duplicate()
	var cycle_rng := RandomNumberGenerator.new()
	cycle_rng.seed = floori(round_seed / 4.0)
	for index: int in range(pack_order.size() - 1, 0, -1):
		var swap_index := cycle_rng.randi_range(0, index)
		var value := pack_order[index]
		pack_order[index] = pack_order[swap_index]
		pack_order[swap_index] = value
	var pack_id: String = pack_order[round_seed % PACK_IDS.size()]
	return _build_pack(round_seed, pack_id, PACKS[pack_id])


static func _build_pack(round_seed: int, pack_id: String, pack: Dictionary) -> Dictionary:
	var rng := RandomNumberGenerator.new()
	rng.seed = round_seed + 1_000_003
	var base_timestamp := int(Time.get_unix_time_from_datetime_dict(FIXED_BASE_DAY))
	var today_start := (
		base_timestamp + (round_seed % DATE_WINDOW_DAY_COUNT) * DAY_SECONDS
	)
	var stage_timestamps: Array[int] = [
		today_start - 90 * DAY_SECONDS + _minutes(10, rng.randi_range(5, 55)),
		today_start - DAY_SECONDS + _minutes(9, rng.randi_range(5, 55)),
		today_start - DAY_SECONDS + _minutes(16, rng.randi_range(5, 55)),
	]
	var current_timestamp := today_start + _minutes(
		rng.randi_range(8, 11),
		rng.randi_range(5, 54),
	)
	var current_time := _time_text(current_timestamp)
	var current_code := current_time.replace(":", "")
	var all_codes: Array[String] = []
	for _index: int in range(3):
		all_codes.append(_unique_code(rng, all_codes, current_code))
	all_codes.append(current_code)

	var stages: Array[Dictionary] = []
	var document_by_room := {}
	var npc_by_room := {}
	for index: int in range(3):
		var room_id: String = pack["rooms"][index]
		var handler: String = pack["handlers"][index]
		var stage := {
			"index": index,
			"room_id": room_id,
			"handler": handler,
			"version": VERSIONS[index],
			"version_label": VERSION_LABELS[index],
			"status": STATUSES[index],
			"timestamp": stage_timestamps[index],
			"date_text": _date_text(stage_timestamps[index]),
			"time_text": _time_text(stage_timestamps[index]),
			"password": all_codes[index],
		}
		stage["contract_body"] = _contract_body(pack, index, handler)
		stages.append(stage)
		document_by_room[room_id] = stage.duplicate(true)
		npc_by_room[room_id] = {
			"display_name": handler,
			"stage_index": index,
			"historical_password": all_codes[index],
			"dialogue": _historical_dialogue(pack["contract"], stage),
		}

	var current := {
		"version": "v1.1",
		"version_label": "SUBMITTED v1.1",
		"status": "SUBMITTED",
		"timestamp": current_timestamp,
		"date_text": _date_text(current_timestamp),
		"time_text": current_time,
		"password": current_code,
		"handler": pack["handlers"][2],
		"room_id": pack["rooms"][2],
		"minutes_before_noon": 12 * 60 - _minute_of_day(current_timestamp),
	}
	var final_room: String = pack["rooms"][2]
	npc_by_room[final_room]["current_password"] = current_code
	npc_by_room[final_room]["dialogue"] += (
		" 我今天上午 %s 已提交 v1.1；档案室当前密码就是提交时间的四位 HHMM：%s。"
		% [current_time, current_code]
	)

	return {
		"pack_id": pack_id,
		"contract_name": pack["contract"],
		"stages": stages,
		"current": current,
		"npc_by_room": npc_by_room,
		"document_by_room": document_by_room,
		"all_codes": all_codes,
	}


static func _contract_body(
	pack: Dictionary,
	stage_index: int,
	handler: String,
) -> String:
	var payment := (
		"启动款40%；试点验收款30%；最终验收款30%"
		if stage_index == 0
		else "启动款30%；试点验收款40%；最终验收款30%"
	)
	var revision_notes: Array[String] = [
		"初稿采用5个工作日验收期及30日运维支持，待管理层与法务审查。",
		"按审查意见将验收期调整为10个工作日，运维支持延长至90日。",
		"商务与法务条款已确认；本文件于昨天下班前形成，等待后续提交记录。",
	]
	var body := (
		"项目范围 / SCOPE：%s\n"
		+ "履约期限 / TERM：生效之日起三个月\n"
		+ "合同金额 / VALUE：%s\n"
		+ "交付里程碑 / MILESTONES：第1月需求确认；第2月试点部署；第3月验收移交\n"
		+ "付款安排 / PAYMENT：%s\n"
		+ "本版修订 / REVISION：%s"
	) % [
		pack["scope"],
		pack["value"],
		payment,
		revision_notes[stage_index],
	]
	if stage_index == 2:
		body += "\n签署人 / SIGNATORY：%s" % handler
	return body


static func _historical_dialogue(contract_name: String, stage: Dictionary) -> String:
	return (
		"我是%s。%s 合同的 %s 在 %s %s 由我经手，当时使用的密码是 %s。"
		% [
			stage["handler"],
			contract_name,
			stage["version_label"],
			stage["date_text"],
			stage["time_text"],
			stage["password"],
		]
	)


static func _unique_code(
	rng: RandomNumberGenerator,
	existing_codes: Array[String],
	current_code: String,
) -> String:
	while true:
		var candidate := "%04d" % rng.randi_range(0, 9999)
		if candidate != current_code and not existing_codes.has(candidate):
			return candidate
	return ""


static func _minutes(hour: int, minute: int) -> int:
	return (hour * 60 + minute) * 60


static func _date_text(timestamp: int) -> String:
	var datetime := Time.get_datetime_dict_from_unix_time(timestamp)
	return "%04d-%02d-%02d" % [datetime["year"], datetime["month"], datetime["day"]]


static func _time_text(timestamp: int) -> String:
	var datetime := Time.get_datetime_dict_from_unix_time(timestamp)
	return "%02d:%02d" % [datetime["hour"], datetime["minute"]]


static func _minute_of_day(timestamp: int) -> int:
	var datetime := Time.get_datetime_dict_from_unix_time(timestamp)
	return int(datetime["hour"]) * 60 + int(datetime["minute"])
