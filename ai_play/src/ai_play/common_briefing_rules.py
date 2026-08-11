"""Shared public rules for all AI Play briefings."""

COMMON_CONTROL_RULES = [
    (
        "可以通过 look 调整视角来观察周围空间，也可以通过前后左右移动在空间中"
        "走动；不要只依据初始视野判断。"
    ),
    (
        "look 使用 yaw 和 pitch，两个轴的范围都是 -45 到 45 度；yaw 为负数时左转、"
        "正数时右转，pitch 为负数时向下、正数时向上。"
    ),
    (
        "例如向左转 30 度使用 {\"type\":\"look\",\"yaw\":-30,\"pitch\":0}。"
    ),
    (
        "look 的角度单位是度；30 到 45 度适合扫视房间，5 到 15 度适合微调准星。"
    ),
    (
        "可以先用 look 环顾四周并灵活调整视角，每次转向后使用 act 返回的新观察；比较当前截图与"
        "上一张截图中地标的位置、大小和遮挡变化，确认实际转向符合预期，并结合地面透视"
        "做深度估计，判断自己与物体的距离。"
    ),
    (
        "act 只会在整个动作批次结束后返回一张截图；探索转向时每个批次只提交一个 look。"
        "不要在同一批次组合互相抵消的 look，也不要提交 yaw、pitch 都为 0 的 look；"
        "否则批末截图可能没有变化。"
    ),
    (
        "像人一样从不同方向观察房间、门口、平台边缘、目标物和障碍物，估计自己与"
        "目标/障碍物的距离，再决定移动路线。"
    ),
    (
        "移动前先通过视角旋转进行空间评估和测距；接近目标或狭窄区域时用小步 move、"
        "probe_interaction 和 act 返回的新观察修正站位，避免碰撞、卡住或从高处摔落损失生命。"
    ),
    (
        "move 和 sprint 的参数范围是 forward -1 到 1、right -1 到 1、duration_ms "
        "50 到 250；forward 控制前后，right 控制左右。输入向量长度会控制实际移动力度，"
        "上限为 1；"
        "单轴绝对值 1 是满强度，单轴 0.2 到 0.4 适合精细对位。"
    ),
    (
        "duration_ms 是按住移动键的毫秒数；250ms 满强度 move 约等于连续走四分之一秒，"
        "满强度 sprint 约等于连续跑四分之一秒。接近普通目标时优先用 100 到 150ms；"
        "穿过狭窄门口或贴近门框时，优先用单轴 0.2 到 0.4、50 到 100ms，每步使用 "
        "act 返回的新观察修正站位，不要在门口连续使用满强度 250ms。"
    ),
    "probe_interaction 只用于在当前视野内对准疑似可交互物并小范围扫描交互提示。",
    (
        "probe_interaction 的 target_x 和 target_y 都是截图归一化坐标，范围 0 到 1；"
        "act 的 schema 为它提供独立分支：actions 必须恰好只包含这一个动作，不能与 move、"
        "look、wait 或其他动作组合，且只能在界面关闭时使用。"
    ),
    (
        "interact 和 interact2 是两个动态交互槽，不是固定含义的操作。每次都必须读取当前 "
        "observation.interface.available_interactions：action 指定可调用的交互槽，prompt 说明"
        "这次交互实际会做什么，binding 只是当前的人类按键提示，不能写入动作对象。没有公开的"
        "交互槽不能调用。"
    ),
    (
        "交互动作对象的格式必须精确为 {\"type\":\"interact\",\"action\":\"interact\"} "
        "或 {\"type\":\"interact\",\"action\":\"interact2\"}。type 固定表示动作类型 "
        "interact，action 才表示当前 observation.interface.available_interactions 中公开的"
        "交互槽 interact 或 interact2。"
    ),
    (
        "坐标探测不是 interact：它的精确格式是 "
        "{\"type\":\"probe_interaction\",\"target_x\":0.5,\"target_y\":0.6}。"
        "target_x 和 target_y 只能用于 probe_interaction，interact 不接受 target、target_x "
        "或 target_y。"
    ),
    (
        "常见无效交互格式及原因：{\"type\":\"interact\"} 缺少 action；"
        "{\"action\":\"interact\"} 缺少 type；"
        "{\"type\":\"interact\",\"target\":\"use\"} 使用了不存在的 target；"
        "{\"type\":\"interact2\"} 错把交互槽写成动作类型；"
        "{\"type\":\"interact\",\"target_x\":0.5,\"target_y\":0.6} 错把探测坐标放入"
        "交互动作。无效格式会被校验拒绝，不会执行任何游戏输入；应依据错误原因修正格式，"
        "不要原样重试。"
    ),
    "每个 act 的 actions 批次必须包含 1 到 3 个动作。",
    "interact、enter_digits、close_ui 等会改变上下文的动作必须放在批次最后。",
    "wait 的 duration_ms 范围是 50 到 2000；不要把 wait 当作默认探索方式。",
    (
        "不要轻易等待；除非视线中出现动态异动的东西，否则应主动观察、转向、靠近、"
        "对准、交互或继续搜索。"
    ),
]
