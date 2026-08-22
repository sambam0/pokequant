#!/bin/bash
# Install Mini host wiring. Does NOT enable scout cron until SUPERVISED_OK + mini-doctor are green.
set -euo pipefail

export PATH="$HOME/Poke/.venv/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
export TZ="${TZ:-Europe/Stockholm}"
POKE="${POKE:-$HOME/Poke}"
cd "$POKE"

if [[ ! -d "$POKE/.venv" ]]; then
  echo "Missing $POKE/.venv — create the venv first" >&2
  exit 1
fi

FOUND="$(command -v pokequant || true)"
EXPECTED="$POKE/.venv/bin/pokequant"
if [[ "$FOUND" != "$EXPECTED" ]]; then
  echo "pokequant must be the venv entry point ($EXPECTED), got: ${FOUND:-none}" >&2
  echo "Never name the Hermes profile pokequant (it shadows this CLI)." >&2
  exit 1
fi

if [[ "${APP_ENV:-}" == "production" && "${DATABASE_URL:-}" == sqlite* ]]; then
  echo "APP_ENV=production rejects sqlite DATABASE_URL" >&2
  exit 1
fi

mkdir -p "$POKE/data/hermes/logs" "$POKE/data/backups"
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/.hermes/profiles/pq-ops/scripts"

# Copy no_agent wrappers into the pq-ops Hermes home (official cron-script-only rule).
cp -f "$POKE/deploy/mini/hermes-scripts/"*.sh "$HOME/.hermes/profiles/pq-ops/scripts/"
chmod +x "$HOME/.hermes/profiles/pq-ops/scripts/"*.sh
chmod +x "$POKE/deploy/mini/"*.sh

# Rewrite LaunchAgent plists for this user.
for src in "$POKE/deploy/mini/LaunchAgents/"*.plist; do
  dest="$HOME/Library/LaunchAgents/$(basename "$src")"
  sed "s|/Users/REPLACE|$HOME|g" "$src" > "$dest"
done

# Homebrew Postgres is a user LaunchAgent (brew services), not a system daemon.
if command -v brew >/dev/null; then
  brew services start postgresql@16 || brew services start postgresql || true
fi

# Load always-on agents. Scout / Hermes cron is NOT loaded here.
launchctl bootout "gui/$(id -u)/com.pokequant.telegram-poll" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.pokequant.watchdog" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.pokequant.caffeinate" 2>/dev/null || true
launchctl bootout "gui/$(id -u)/com.pokequant.pgdump" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.pokequant.telegram-poll.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.pokequant.watchdog.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.pokequant.caffeinate.plist"
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.pokequant.pgdump.plist"

echo "Installed Mini LaunchAgents + pq-ops scripts."
echo "Next: hermes profile create pq-ops (never pokequant), pq-ops setup --portal, alembic upgrade head."
echo "Do not write SUPERVISED_OK or enable tradera-scan until mini-doctor is green after reboot."
