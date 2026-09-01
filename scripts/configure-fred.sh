#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env"

printf 'Create a free FRED key at:\n  https://fred.stlouisfed.org/docs/api/api_key.html\n\n'
IFS= read -r -s -p 'FRED API key (input hidden): ' FRED_KEY
printf '\n'

if [[ ! "$FRED_KEY" =~ ^[a-z0-9]{32}$ ]]; then
  echo 'Invalid key format: expected 32 lowercase letters/numbers.' >&2
  unset FRED_KEY
  exit 2
fi

FRED_API_KEY_INPUT="$FRED_KEY" ENV_FILE="$ENV_FILE" python3 - <<'PY'
import json
import os
import re
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

key = os.environ["FRED_API_KEY_INPUT"]
env_file = Path(os.environ["ENV_FILE"])
params = urlencode({
    "series_id": "FEDFUNDS",
    "api_key": key,
    "file_type": "json",
    "limit": 1,
})
with urlopen(f"https://api.stlouisfed.org/fred/series?{params}", timeout=30) as response:
    payload = json.loads(response.read())
if not payload.get("seriess"):
    raise SystemExit("FRED accepted the request but returned no validation series")

existing = env_file.read_text(encoding="utf-8") if env_file.exists() else ""
line = f"FRED_API_KEY={key}"
if re.search(r"(?m)^FRED_API_KEY=.*$", existing):
    updated = re.sub(r"(?m)^FRED_API_KEY=.*$", line, existing)
else:
    separator = "" if not existing or existing.endswith("\n") else "\n"
    updated = existing + separator + line + "\n"
env_file.write_text(updated, encoding="utf-8")
os.chmod(env_file, 0o600)
PY

unset FRED_KEY
echo "FRED configured and validated in $ENV_FILE (mode 600)."
