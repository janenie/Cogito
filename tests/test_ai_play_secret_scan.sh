#!/usr/bin/env bash
set -euo pipefail

scanner="$(pwd)/tests/check_ai_play_secrets.sh"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT

git -C "$fixture" init -q
mkdir -p "$fixture/ai_play/src" "$fixture/ai_play/tests"

env_name="AI_PLAY_API""_KEY"
field_name="api""_key"
env_secret="synthetic-env-secret"
field_secret="synthetic-field-secret"
printf '%s = %s\n' "$env_name" "$env_secret" > "$fixture/ai_play/src/env.py"
printf '%s = "%s"\n' "$field_name" "$field_secret" > "$fixture/ai_play/tests/field.py"
printf '%s=config.%s\n' "$field_name" "$field_name" > "$fixture/ai_play/src/sdk.py"
printf '%s=%s\n' "$env_name" "$env_secret" > "$fixture/ai_play/.env.example"
git -C "$fixture" add .

set +e
output="$($scanner "$fixture" 2>&1)"
status=$?
set -e

test "$status" -ne 0
sorted_output="$(printf '%s\n' "$output" | LC_ALL=C sort)"
test "$sorted_output" = $'ai_play/src/env.py\nai_play/tests/field.py'
test "${output#*${env_secret}}" = "$output"
test "${output#*${field_secret}}" = "$output"
