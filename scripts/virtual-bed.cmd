@echo off
rem Run the virtual bed on this laptop with local Firebase emulators.
setlocal
cd /d "%~dp0.." || exit /b 1
if not exist ".venv\Scripts\python.exe" (echo Run scripts\setup.cmd first. & exit /b 1)

set "TEXTILE_PROJECT=demo-textilesense-bed"
set "TEXTILE_EMULATOR_PORT=8180"
set "EXPO_PUBLIC_PROJECT_ID=demo-textilesense-bed"
set "EXPO_PUBLIC_SESSION=virtual-bed"
set "EXPO_PUBLIC_AUTH_PORT=9199"
set "EXPO_PUBLIC_FIRESTORE_PORT=8180"
set "EXPO_PUBLIC_EMULATOR_HOST=127.0.0.1"
set "FIREBASE_EMULATORS_PATH=%CD%\.cache"

echo Building the browser copy of the phone app (about 30 seconds)...
pushd mobile || exit /b 1
call npx --no-install expo export --platform web --output-dir ../.cache/virtual-web >nul || (popd & exit /b 1)
popd
call node_modules\.bin\firebase.cmd emulators:exec --ui --config firebase.virtual.json --project demo-textilesense-bed --only auth,firestore ".venv\Scripts\python.exe -m virtual_bed.launch"
exit /b %errorlevel%
