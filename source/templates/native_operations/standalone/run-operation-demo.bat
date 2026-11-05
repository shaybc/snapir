@echo off
rem Launch the existing operation runner with the prepared demo database.
setlocal DisableDelayedExpansion
if not "%~1"=="" goto supplied_request
call "%~dp0run-operation.bat" "%~dp0standalone\demo-request.xml" --demo
exit /b %ERRORLEVEL%
:supplied_request
call "%~dp0run-operation.bat" %* --demo
exit /b %ERRORLEVEL%
