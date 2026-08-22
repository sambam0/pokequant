#!/bin/bash
set -euo pipefail
export PATH="$HOME/Poke/.venv/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export TZ="${TZ:-Europe/Stockholm}"
cd "$HOME/Poke"
set -a
# shellcheck disable=SC1091
source "$HOME/Poke/.env"
set +a

DEST="${POKE_PGDUMP_DIR:-$HOME/Poke/data/backups}"
mkdir -p "$DEST"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
FILE="$DEST/pokequant-$STAMP.sql"
pg_dump "$DATABASE_URL" > "$FILE"
# Optional: encrypt with age/gpg if POKE_PGDUMP_RECIPIENT is set.
if [[ -n "${POKE_PGDUMP_RECIPIENT:-}" ]] && command -v age >/dev/null; then
  age -r "$POKE_PGDUMP_RECIPIENT" -o "$FILE.age" "$FILE"
  rm -f "$FILE"
fi
date -u +%Y-%m-%dT%H:%M:%SZ > "$HOME/Poke/data/hermes/last_pg_dump"
