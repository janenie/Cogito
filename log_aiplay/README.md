# AI Play 结果日志

日志按模型和任务组织：

```text
log_aiplay/
└── <model>/
    └── task-<scenario_id>.log
```

例如：`claude-opus-5/task-put_book.log`。模型目录使用启动参数中的模型 ID；任务文件使用
`ai_play.scenarios` 注册的稳定任务 ID。每个文件开头至少记录 `task`、`model`、思考强度、
AWM 模式和请求运行次数，并逐次记录可信轨迹地址、supervisor 终态、步数和公开进度。

同一模型和任务需要保留多个批次时，使用
`task-<scenario_id>--<benchmark_id>.log`，不要覆盖旧结果。能力统计只采用 supervisor 的正式
`game_over`；`stopped`、断连和其他基础设施中断必须单独标记。日志不得包含凭据、隐藏答案、
图片内容或模型的隐藏推理链。
