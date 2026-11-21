@echo off
rem Serve the Expo app to Expo Go on your phone. Add --tunnel if the phone
rem cannot reach this laptop over Wi-Fi (for example on campus networks).
setlocal
cd /d "%~dp0..\mobile" || exit /b 1
if not exist ".env.local" (echo Run scripts\hosted-setup.cmd first so the app knows your Firebase project. & exit /b 1)
set "MODE=--lan"
if /i "%~1"=="--tunnel" set "MODE=--tunnel ngrok"
echo.
echo   Phone and laptop need the same Wi-Fi for --lan. Then:
echo     iPhone: scan the QR code with the Camera app.
echo     Android: open Expo Go and tap "Scan QR code".
echo.
call npx expo start %MODE% --clear
exit /b %errorlevel%
