@echo off
rem Run the virtual bed against your hosted Firebase project (for the phone).
setlocal
cd /d "%~dp0.." || exit /b 1
if not exist ".venv\Scripts\python.exe" (echo Run scripts\setup.cmd first. & exit /b 1)
if not exist "hosted.env" (echo Copy hosted.env.example to hosted.env and fill it in. See PHONE.md. & exit /b 1)
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("hosted.env") do set "%%a=%%b"
set "FIRESTORE_EMULATOR_HOST="
set "FIREBASE_AUTH_EMULATOR_HOST="
set "TEXTILE_EMULATOR_PORT="
.venv\Scripts\python.exe -m virtual_bed.hosted check || (echo Fix the item above, then run this again. & exit /b 1)
.venv\Scripts\python.exe -m virtual_bed.launch
exit /b %errorlevel%
