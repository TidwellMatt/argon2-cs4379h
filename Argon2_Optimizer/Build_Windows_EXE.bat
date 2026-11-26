@echo off
setlocal
cd /d "%~dp0"
echo Building Argon2 Optimizer for Windows x64 with bundled GPU engine...
if not exist .venv\Scripts\python.exe (
  python -m venv .venv
  if errorlevel 1 goto fail
)
.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-build.txt
if errorlevel 1 goto fail
.venv\Scripts\python.exe build_windows.py
if errorlevel 1 goto fail
if not exist dist\Argon2Optimizer.exe goto fail
echo.
echo Build and package self-test complete: %CD%\dist\Argon2Optimizer.exe
echo Share the EXE itself. No Python or separate Hashcat download is required by recipients.
explorer "%CD%\dist"
pause
exit /b 0
:fail
echo Build failed. Check the output above and dist\package_selftest.txt if present.
pause
exit /b 1
