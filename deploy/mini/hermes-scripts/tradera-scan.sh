#!/bin/bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "$0")/_env.sh"
if [[ ! -s "$HOME/Poke/data/hermes/SUPERVISED_OK" ]]; then
  echo "SUPERVISED_OK missing; refusing scan" >&2
  exit 1
fi
exec pokequant scan --send-telegram
