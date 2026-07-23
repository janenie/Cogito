#!/usr/bin/env bash
set -euo pipefail

repo="${1:-.}"
cd "$repo"

files=()
if git rev-parse --show-toplevel >/dev/null 2>&1; then
	file_source=(git ls-files -z)
else
	file_source=(find ai_play addons/cogito/AIPlay tests -type f -not -path '*/__pycache__/*' -not -name '*.pyc' -print0)
fi
while IFS= read -r -d '' path; do
	case "$path" in
		*.example)
			;;
		ai_play/*|addons/cogito/AIPlay/*|tests/ai_play/*|tests/*ai_play*)
			files+=("$path")
			;;
	esac
done < <("${file_source[@]}")

if ((${#files[@]} == 0)); then
	exit 0
fi

status=0
if command -v rg >/dev/null 2>&1; then
	rg -l --no-messages \
		-e 'AI_PLAY_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]#]+' \
		-e "api_key[[:space:]]*=[[:space:]]*['\"]" \
		-- "${files[@]}" || status=$?
else
	grep -Il -E \
		-e 'AI_PLAY_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]#]+' \
		-e "api_key[[:space:]]*=[[:space:]]*['\"]" \
		-- "${files[@]}" || status=$?
fi

if ((status == 1)); then
	exit 0
fi
exit 1
