@echo off
setlocal DisableDelayedExpansion
set "JAVA_EXE=java"
if defined JAVA_HOME set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
"%JAVA_EXE%" -jar "%~dp0..\server\fixture-server.jar" %*
exit /b %ERRORLEVEL%
