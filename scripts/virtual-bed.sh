#!/usr/bin/env bash
# Launch the interactive virtual mat on Linux or macOS.
set -eu
cd "$(dirname "$0")/.."
export EXPO_PUBLIC_SESSION=virtual-bed
if [[ "${1:-}" = "--hosted" ]]; then
  : "${TEXTILE_PROJECT:?Set the approved Firebase project ID}"
  : "${EXPO_PUBLIC_API_KEY:?Set its Firebase web API key}"
  [[ "$TEXTILE_PROJECT" != demo-* ]] || { echo "Use a hosted project ID"; exit 1; }
  unset FIRESTORE_EMULATOR_HOST FIREBASE_AUTH_EMULATOR_HOST
  export EXPO_PUBLIC_PROJECT_ID="$TEXTILE_PROJECT"
elif [[ $# = 0 ]]; then
  export TEXTILE_PROJECT=demo-textilesense-bed
  export TEXTILE_EMULATOR_PORT=8180
  export EXPO_PUBLIC_PROJECT_ID=demo-textilesense-bed
  export EXPO_PUBLIC_AUTH_PORT=9199
  export EXPO_PUBLIC_FIRESTORE_PORT=8180
  export EXPO_PUBLIC_EMULATOR_HOST=127.0.0.1
  export FIREBASE_EMULATORS_PATH="$PWD/.cache"
else
  echo "Usage: bash scripts/virtual-bed.sh [--hosted]" >&2; exit 1
fi
(cd mobile && npx --no-install expo export --platform web --output-dir ../.cache/virtual-web)
if [[ "${1:-}" = "--hosted" ]]; then
  exec .venv/bin/python -m virtual_bed.launch
fi
exec node_modules/.bin/firebase emulators:exec --ui --config firebase.virtual.json --project demo-textilesense-bed --only auth,firestore '.venv/bin/python -m virtual_bed.launch'
