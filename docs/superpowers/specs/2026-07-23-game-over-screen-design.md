# Find Contract Game Over Screen Design

## Goal

When the Find Contract game reaches a terminal result, show an unmistakable
full-screen result and prevent the player or AI from performing more actions.

## Terminal Results

- Correct password: success, reason `correct_password`.
- Wrong password: failure, reason `wrong_password`.
- 1000 AI requests reached: failure, reason `max_requests`.

Password results apply to both manual play and AI play. The request limit only
applies to AI play.

## Presentation

The result screen displays `游戏结束`, followed by either `解谜成功` or
`解谜失败`, plus a short reason. It has no continue or dismiss control.

The screen uses an opaque full-viewport input-blocking background and remains
active while the SceneTree is paused.

## Architecture

`AIPlayGameOverScreen` owns presentation and pauses the SceneTree. The existing
Find Contract terminal monitor owns a reference to that screen and exposes
`show_result(outcome, reason)`. It displays keypad outcomes directly so manual
play works without a sidecar.

`AIPlayController` asks the terminal monitor to display every accepted terminal
result. This covers local password results and the local or remote request-limit
paths. Repeated terminal signals are idempotent.

## Verification

Automated Godot tests verify Chinese result copy, SceneTree pause, password
outcomes, request-limit outcomes, and duplicate terminal events. A scene wiring
check verifies the Lobby contains the result screen.
