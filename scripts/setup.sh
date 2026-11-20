#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
command -v ffmpeg >/dev/null || { echo 'Install FFmpeg before running setup.' >&2; exit 1; }
"${PYTHON:-python3.12}" -m venv .venv
if [ "$(uname -s)" = Linux ]; then
  .venv/bin/python -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
else
  .venv/bin/python -m pip install torch==2.15.0
fi
.venv/bin/python -m pip install -r requirements.txt
npm ci
(cd mobile && npm ci && npx expo export --platform web)
.venv/bin/python -m playwright install chromium ffmpeg
