@echo off
rem Ensure project dependencies are available before launching the Snapir CLI.
setlocal
pushd "%~dp0"
if errorlevel 1 exit /b 1

if not exist ".venv\Scripts\python.exe" (
    call :create_environment
    if errorlevel 1 goto environment_failed
)

".venv\Scripts\python.exe" -m pip install -r "requirements.txt"
set "exit_code=%errorlevel%"
if not "%exit_code%"=="0" goto finish
cls

pushd "source"
if errorlevel 1 (
    set "exit_code=1"
    goto finish
)
"%~dp0.venv\Scripts\python.exe" -m cli %*
set "exit_code=%errorlevel%"
popd
goto finish

:environment_failed
set "exit_code=%errorlevel%"
echo Error: Could not create "%~dp0.venv". Check your installed Python and try again. 1>&2

:finish
popd
exit /b %exit_code%

:create_environment
where py >nul 2>&1
if errorlevel 1 goto use_python
py -3 -m venv ".venv"
exit /b %errorlevel%

:use_python
where python >nul 2>&1
if errorlevel 1 (
    echo Error: Install Python 3 and make py or python available on PATH. 1>&2
    exit /b 1
)
python -m venv ".venv"
exit /b %errorlevel%
