@echo off
setlocal
cd /d "%~dp0"
if defined FORMAT_LIBRARY_PYTHON (
  "%FORMAT_LIBRARY_PYTHON%" -m format_library %*
) else if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" -m format_library %*
) else (
  python -m format_library %*
)
set "tool_exit=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %tool_exit%
