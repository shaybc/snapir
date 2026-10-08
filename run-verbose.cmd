@echo off
rem Start the existing migration launcher with verbose diagnostics enabled.
call "%~dp0run.cmd" --verbose %*
exit /b %errorlevel%
