@echo off
rem One-time setup of a hosted Firebase project: rules, viewer, session, app config.
setlocal
cd /d "%~dp0.." || exit /b 1
if not exist ".venv\Scripts\python.exe" (echo Run scripts\setup.cmd first. & exit /b 1)
if not exist "hosted.env" (echo Copy hosted.env.example to hosted.env and fill it in. See PHONE.md. & exit /b 1)
for /f "usebackq eol=# tokens=1,* delims==" %%a in ("hosted.env") do set "%%a=%%b"
set "FIRESTORE_EMULATOR_HOST="
set "TEXTILE_EMULATOR_PORT="
set "VIEWER=%~1"
if "%VIEWER%"=="" set /p "VIEWER=Email for the phone's viewer account: "
.venv\Scripts\python.exe -m virtual_bed.hosted setup --email "%VIEWER%"
exit /b %errorlevel%
