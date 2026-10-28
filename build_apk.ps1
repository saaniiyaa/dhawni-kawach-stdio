<#
.SYNOPSIS
    DHWANI-KAVACH Android APK Build and Sync Automation Script (PowerShell)
.DESCRIPTION
    Automates Capacitor sync, manifest checks, and Gradle debug APK compilation.
#>

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  DHWANI-KAVACH -- CAPACITOR ANDROID APK BUILD SCRIPT" -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"

# 1. Check Node/NPM
try {
    $nodeVer = & node -v
    Write-Host "[✓] Node.js found: $nodeVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Node.js is not found in PATH. Please install Node.js (v18+)." -ForegroundColor Red
    exit 1
}

# 2. Check Java
try {
    $javaVer = & java -version 2>&1 | Select-Object -First 1
    Write-Host "[✓] Java environment: $javaVer" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Java JDK is not found in PATH. Please install JDK 17+ and configure JAVA_HOME." -ForegroundColor Red
    exit 1
}

# 3. Capacitor Sync
Write-Host "`n[STEP 1/3] Syncing web assets into Android project..." -ForegroundColor Yellow
& npm.cmd run cap:sync

# 4. Compile with Gradle
Write-Host "`n[STEP 2/3] Building Debug APK via Gradle..." -ForegroundColor Yellow
Push-Location android
try {
    & .\gradlew.bat assembleDebug
    Write-Host "[✓] Gradle compilation successful!" -ForegroundColor Green
} catch {
    Write-Host "[WARNING] Gradle command-line build failed or timed out." -ForegroundColor Yellow
    Write-Host "You can also open the project in Android Studio: 'npx cap open android'" -ForegroundColor Gray
} finally {
    Pop-Location
}

# 5. Check APK output
$apkSrc = "android\app\build\outputs\apk\debug\app-debug.apk"
$apkDest = "dist\DhwaniKavach-debug.apk"

Write-Host "`n[STEP 3/3] Checking output artifacts..." -ForegroundColor Yellow
if (Test-Path $apkSrc) {
    if (-not (Test-Path "dist")) {
        New-Item -ItemType Directory -Path "dist" | Out-Null
    }
    Copy-Item -Path $apkSrc -Destination $apkDest -Force
    Write-Host "`n================================================================" -ForegroundColor Green
    Write-Host " [SUCCESS] APK BUILT SUCCESSFULLY!" -ForegroundColor Green
    Write-Host " Final APK Location: $apkDest" -ForegroundColor White
    Write-Host " Native APK Location: $apkSrc" -ForegroundColor Gray
    Write-Host "================================================================" -ForegroundColor Green
} else {
    Write-Host "[INFO] Project synced. Run 'npx cap open android' to build or debug in Android Studio." -ForegroundColor Cyan
}
