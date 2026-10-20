@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Build Composer Mapper and generate a scoped vault from prompted paths.

pushd "%~dp0" || exit /b 1

set "mapperRoot=C:\workspace\composer\workspace"
set "mapperVault=C:\workspace\composer-map"
set /p "mapperRoot=Composer root [%mapperRoot%]: "
set /p "mapperVault=Output vault [%mapperVault%]: "

echo Building Composer Mapper...
call mvn -q package
if errorlevel 1 goto buildFailed

echo Generating Composer map...
java -jar "target\composer-mapper-1.1.1-jar-with-dependencies.jar" --root "%mapperRoot%" --vault "%mapperVault%" --vault-layout scoped --workspace-id "full-composer" --md true
set "mapperExitCode=%errorlevel%"
goto finish

:buildFailed
set "mapperExitCode=%errorlevel%"
echo Build failed. Composer map generation was not started.

:finish
popd
endlocal & exit /b %mapperExitCode%
