#!/usr/bin/env bash
set -euo pipefail

script="ai_play/start_ai.sh"

test -x "$script"
grep -q 'PYTHONPATH=ai_play/src' "$script"
grep -q -- '-m ai_play.main "$@"' "$script"

fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT

cp "$script" "$fixture/start_ai.sh"
chmod +x "$fixture/start_ai.sh"
mkdir -p "$fixture/../.venv/bin"

cat > "$fixture/../.venv/bin/python" <<'PY'
#!/usr/bin/env bash
printf 'cwd=%s\n' "$(pwd)"
printf 'PYTHONPATH=%s\n' "${PYTHONPATH:-}"
printf 'args=%s\n' "$*"
PY
chmod +x "$fixture/../.venv/bin/python"

output="$(cd /tmp && "$fixture/start_ai.sh" --resume)"

grep -q "cwd=$(cd "$fixture/.." && pwd)" <<<"$output"
grep -q "PYTHONPATH=ai_play/src" <<<"$output"
grep -q "args=-m ai_play.main --resume" <<<"$output"
