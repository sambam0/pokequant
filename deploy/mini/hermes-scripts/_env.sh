#!/bin/bash
set -euo pipefail
export PATH="$HOME/Poke/.venv/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export TZ="${TZ:-Europe/Stockholm}"
cd "$HOME/Poke"
set -a
# shellcheck disable=SC1091
source "$HOME/Poke/.env"
set +a
