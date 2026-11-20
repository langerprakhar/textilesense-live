#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
if [ "${1:-}" = "--running-emulators" ]; then
  exec .venv/bin/python -m proof.launch_demo
fi
exec node_modules/.bin/firebase emulators:exec --only firestore,auth --project demo-textilesense '.venv/bin/python -m proof.launch_demo'
