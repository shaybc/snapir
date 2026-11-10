@echo off
rem Inspect saved migration evidence offline without installing or changing anything.
setlocal
pushd "%~dp0source"
if errorlevel 1 exit /b 1
set "PYTHONDONTWRITEBYTECODE=1"
if exist "%~dp0.venv\Scripts\python.exe" (
    "%~dp0.venv\Scripts\python.exe" -B -m tools.run_diagnostics %*
) else (
    python -B -m tools.run_diagnostics %*
)
set "diagnostic_exit=%errorlevel%"
popd
echo.
pause
exit /b %diagnostic_exit%
