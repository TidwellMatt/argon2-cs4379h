@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\pythonw.exe (
  echo Run setup_windows.bat first, or Build_Windows_EXE.bat to create the standalone executable.
  pause
  exit /b 1
)
start "" .venv\Scripts\pythonw.exe desktop.py
