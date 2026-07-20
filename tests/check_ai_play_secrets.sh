#!/usr/bin/env bash
set -euo pipefail

repo="${1:-.}"
cd "$repo"

files=()
while IFS= read -r -d '' path; do
	case "$path" in
		*.example)
			;;
		ai_play/*|addons/cogito/AIPlay/*|tests/ai_play/*|tests/*ai_play*)
			files+=("$path")
			;;
	esac
done < <(git ls-files -z)

if ((${#files[@]} == 0)); then
	exit 0
fi

status=0
rg -l --no-messages \
	-e 'AI_PLAY_API_KEY[[:space:]]*=[[:space:]]*[^[:space:]#]+' \
	-e "api_key[[:space:]]*=[[:space:]]*['\"]" \
	-- "${files[@]}" || status=$?

if ((status == 1)); then
	exit 0
fi
exit 1
