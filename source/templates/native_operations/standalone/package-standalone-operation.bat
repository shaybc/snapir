@echo off
rem Copy the operation project and its external demo assets without building a different operation.
setlocal DisableDelayedExpansion
pushd "%~dp0" || exit /b 1
set "JAVA_EXE=java"
set "JAVAC_EXE=javac"
if defined JAVA_HOME set "JAVA_EXE=%JAVA_HOME%\bin\java.exe"
if defined JAVA_HOME set "JAVAC_EXE=%JAVA_HOME%\bin\javac.exe"
set "NATIVE_PROJECT=%CD%"
if exist standalone\pom.xml set "NATIVE_PROJECT=%CD%\standalone"
if not exist target\standalone-packager-classes mkdir target\standalone-packager-classes
call mvn --batch-mode -q -f "%NATIVE_PROJECT%\standalone\packaging\pom.xml" org.apache.maven.plugins:maven-dependency-plugin:3.8.1:copy-dependencies "-DoutputDirectory=%CD%\target\standalone-packager-lib" 1>&2
if errorlevel 1 goto failed
"%JAVAC_EXE%" -encoding UTF-8 -cp "target\standalone-packager-lib\*" -d target\standalone-packager-classes "%NATIVE_PROJECT%\standalone\DemoBinding.java" "%NATIVE_PROJECT%\standalone\packaging\PackageFiles.java" "%NATIVE_PROJECT%\standalone\packaging\PackageDemoAssets.java" "%NATIVE_PROJECT%\standalone\packaging\PackageProjectFiles.java" "%NATIVE_PROJECT%\standalone\packaging\PackageMicroserviceValues.java" "%NATIVE_PROJECT%\standalone\packaging\PackageSharedDependencies.java" "%NATIVE_PROJECT%\standalone\packaging\StandalonePackage.java" 1>&2
if errorlevel 1 goto failed
"%JAVA_EXE%" -cp "target\standalone-packager-classes;target\standalone-packager-lib\*" StandalonePackage "%CD%"
set "RUN_EXIT=%ERRORLEVEL%"
popd
exit /b %RUN_EXIT%
:failed
set "RUN_EXIT=%ERRORLEVEL%"
echo Operation project packaging failed. Existing project files and packages were preserved. 1>&2
popd
exit /b %RUN_EXIT%
