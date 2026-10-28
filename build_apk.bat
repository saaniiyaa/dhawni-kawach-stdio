@echo off
setlocal enabledelayedexpansion

echo ================================================================
echo   DHWANI-KAVACH -- CAPACITOR ANDROID APK BUILD AUTOMATION
echo ================================================================
echo.

:: 1. Check Node.js and NPM
where npm.cmd >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Node.js / npm is not found in PATH.
    echo Please install Node.js (v18+) from https://nodejs.org/
    pause
    exit /b 1
)

:: 2. Check Java / JDK
where java >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Java JDK is not found in PATH.
    echo Please install OpenJDK 17 or 21 and configure JAVA_HOME.
    pause
    exit /b 1
)

echo [STEP 1/4] Syncing web assets and Capacitor configurations...
call npm.cmd run cap:sync
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Capacitor sync failed!
    pause
    exit /b 1
)

echo.
echo [STEP 2/4] Verifying Android native project...
if not exist "android\app\src\main\AndroidManifest.xml" (
    echo [INFO] Adding Android platform...
    call npx.cmd cap add android
    call npm.cmd run cap:sync
)

echo.
echo [STEP 3/4] Building Android Debug APK with Gradle...
cd android
call gradlew.bat assembleDebug
set GRADLE_STATUS=%ERRORLEVEL%
cd ..

if %GRADLE_STATUS% neq 0 (
    echo.
    echo [WARNING] Gradle command-line build encountered an issue.
    echo If Android SDK is not in PATH/ANDROID_HOME, you can open the project in Android Studio:
    echo    npx cap open android
    echo Or ensure ANDROID_HOME and command-line tools are installed.
    pause
    exit /b %GRADLE_STATUS%
)

echo.
echo [STEP 4/4] Locating generated APK...
set APK_PATH=android\app\build\outputs\apk\debug\app-debug.apk
if exist "%APK_PATH%" (
    if not exist "dist" mkdir "dist"
    copy /Y "%APK_PATH%" "dist\DhwaniKavach-debug.apk" >nul
    echo.
    echo ================================================================
    echo  [SUCCESS] APK BUILD COMPLETED!
    echo  Output Location: dist\DhwaniKavach-debug.apk
    echo  Native Location: %APK_PATH%
    echo ================================================================
) else (
    echo [INFO] Build completed. Check android\app\build\outputs\apk\
)

echo.
pause
