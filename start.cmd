@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 app.py
  pause
  exit /b
)
set "GC_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if exist "%GC_PYTHON%" (
  "%GC_PYTHON%" app.py
) else (
  python app.py
)
pause
