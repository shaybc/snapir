@echo off
setlocal EnableExtensions DisableDelayedExpansion
rem Build Composer Mapper and generate a scoped vault from prompted paths.

pushd "%~dp0" || exit /b 1

set "mapperRoot=C:\workspace\composer\workspace"
set "mapperVault=C:\workspace\composer-map"
set /p "mapperRoot=Composer root [%mapperRoot%]: "
set /p "mapperVault=Output vault [%mapperVault%]: "
set "mapperAnalysis=indexed-v1"
set "mapperWorkspace=full-composer"
set /p "mapperAnalysis=Analysis format: legacy or indexed-v1 [%mapperAnalysis%]: "
set /p "mapperWorkspace=Stable workspace ID [%mapperWorkspace%]: "

echo Building Composer Mapper...
call mvn -q -f ..\pom.xml package
if errorlevel 1 goto buildFailed

echo Generating Composer map...
java -Xmx768m -jar "target\composer-mapper-1.1.1-jar-with-dependencies.jar" --root "%mapperRoot%" --vault "%mapperVault%" --vault-layout scoped --workspace-id "%mapperWorkspace%" --md true --analysis-format "%mapperAnalysis%"
set "mapperExitCode=%errorlevel%"
goto finish

:buildFailed
set "mapperExitCode=%errorlevel%"
echo Build failed. Composer map generation was not started.

:finish
popd
endlocal & exit /b %mapperExitCode%
