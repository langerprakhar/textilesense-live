@echo off
setlocal
cd /d "%~dp0.." || exit /b 1
py -3.12 --version || (echo Install 64-bit Python 3.12 with the Windows Python launcher. & exit /b 1)
node --version || (echo Install Node.js 24 and reopen Command Prompt. & exit /b 1)
java -version || (echo Install JDK 21 and reopen Command Prompt. & exit /b 1)

py -3.12 -m venv .venv || exit /b 1
.venv\Scripts\python.exe -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu || exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt || exit /b 1
call npm ci || exit /b 1
pushd mobile || exit /b 1
call npm ci || exit /b 1
popd
echo Setup complete. Run scripts\virtual-bed.cmd to launch the virtual pressure mat.
