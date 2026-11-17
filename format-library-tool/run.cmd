@echo off
setlocal
cd /d "%~dp0"
if defined FORMAT_LIBRARY_PYTHON (
  set "tool_python=%FORMAT_LIBRARY_PYTHON%"
) else if exist "%~dp0.venv\Scripts\python.exe" (
  set "tool_python=%~dp0.venv\Scripts\python.exe"
) else (
  set "tool_python=python"
)
"%tool_python%" -m format_library.bootstrap %*
if errorlevel 1 goto startup_failed
"%tool_python%" -m format_library %*
set "tool_exit=%ERRORLEVEL%"
goto finish
:startup_failed
set "tool_exit=%ERRORLEVEL%"
echo Dependency setup failed. The format library tool was not started.
:finish
if "%~1"=="" pause
exit /b %tool_exit%
