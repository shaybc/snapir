@echo off
setlocal DisableDelayedExpansion
pushd "%~dp0" || exit /b 1
set "JAVA_EXE=java"
set "JAVAC_EXE=javac"
if defined JAVA_HOME set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
if defined JAVA_HOME set "JAVAC_EXE=%JAVA_HOME%\bin\javac.exe"
rem This test-only helper is converter-owned source, not a public Maven artifact.
if exist standalone\test-support\behavior-verification\pom.xml (
    call mvn --batch-mode -q -f standalone\test-support\behavior-verification\pom.xml -DskipTests install 1>&2
    if errorlevel 1 goto failed
)
call mvn --batch-mode -q -DskipTests clean package org.apache.maven.plugins:maven-dependency-plugin:3.8.1:copy-dependencies -DincludeScope=runtime -DoutputDirectory=target/standalone-lib 1>&2
if errorlevel 1 goto failed
if not exist target\standalone-classes mkdir target\standalone-classes
"%JAVAC_EXE%" -encoding UTF-8 -cp "target\classes;target\standalone-lib\*" -d target\standalone-classes standalone\RuntimeDatabase.java standalone\StandaloneOperationRunner.java standalone\StandaloneLaunch.java standalone\DemoBinding.java standalone\DemoServerProcess.java 1>&2
if errorlevel 1 goto failed
"%JAVA_EXE%" -Dfile.encoding=UTF-8 -cp "target\standalone-classes;target\classes;target\standalone-lib\*;..\..\lib\*;lib\*" StandaloneLaunch "standalone\operation.json" %*
set "RUN_EXIT=%ERRORLEVEL%"
popd
exit /b %RUN_EXIT%
:failed
set "RUN_EXIT=%ERRORLEVEL%"
popd
exit /b %RUN_EXIT%
