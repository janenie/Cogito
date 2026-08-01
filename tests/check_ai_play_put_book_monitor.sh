#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

log_file="$(mktemp -t cogito_put_book_headless.XXXXXX.log)"
godot_pid=""

cleanup() {
	if [[ -n "$godot_pid" ]]; then
		kill -TERM -- "-${godot_pid}" 2>/dev/null || kill -TERM "$godot_pid" 2>/dev/null || true
		for _attempt in 1 2; do
			kill -0 -- "-${godot_pid}" 2>/dev/null || break
			sleep 1
		done
		if kill -0 -- "-${godot_pid}" 2>/dev/null; then
			kill -KILL -- "-${godot_pid}" 2>/dev/null || kill -KILL "$godot_pid" 2>/dev/null || true
		fi
		wait "$godot_pid" 2>/dev/null || true
	fi
	rm -f "$log_file"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

godot_bin="${GODOT_BIN:-godot}"
python3 -c \
	'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
	"$godot_bin" --headless --path . --script tests/ai_play/test_ai_play_put_book_monitor.gd \
	-- --ai-play-scenario=put_book >"$log_file" 2>&1 &
godot_pid=$!
deadline=$((SECONDS + 40))

while kill -0 "$godot_pid" 2>/dev/null; do
	if (( SECONDS >= deadline )); then
		kill -TERM -- "-${godot_pid}" 2>/dev/null || kill -TERM "$godot_pid" 2>/dev/null || true
		for _attempt in 1 2; do
			kill -0 -- "-${godot_pid}" 2>/dev/null || break
			sleep 1
		done
		if kill -0 -- "-${godot_pid}" 2>/dev/null; then
			kill -KILL -- "-${godot_pid}" 2>/dev/null || kill -KILL "$godot_pid" 2>/dev/null || true
		fi
		wait "$godot_pid" 2>/dev/null || true
		godot_pid=""
		cat "$log_file"
		exit 1
	fi
	sleep 1
done

set +e
wait "$godot_pid"
status=$?
set -e
godot_pid=""

if (( status != 0 )); then
	cat "$log_file"
	exit 1
fi

if grep -Eq 'SCRIPT ERROR|Parse Error|Failed to load script|invalid UID' "$log_file"; then
	cat "$log_file"
	exit 1
fi

# Loading the full Lobby under Godot's dummy headless renderer reproducibly emits
# these two shutdown-only leak signatures. Reject every other ERROR line.
if awk '
	/^ERROR:/ \
		&& $0 != "ERROR: 21 resources still in use at exit (run with --verbose for details)." \
		&& $0 != "ERROR: 3 RID allocations of type '\''N13RendererDummy15MaterialStorage11DummyShaderE'\'' were leaked at exit." \
		{ unexpected = 1 }
	END { exit unexpected ? 0 : 1 }
' "$log_file"; then
	cat "$log_file"
	exit 1
fi

if ! grep -Fxq 'AIPlay put-book monitor test passed' "$log_file"; then
	cat "$log_file"
	exit 1
fi

echo "AIPlay put-book monitor test passed"
