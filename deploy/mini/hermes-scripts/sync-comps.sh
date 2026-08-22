#!/bin/bash
set -euo pipefail
# shellcheck disable=SC1091
source "$(dirname "$0")/_env.sh"
exec pokequant sync-comps
