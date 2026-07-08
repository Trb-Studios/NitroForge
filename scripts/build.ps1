# Nitro Forge release build: sidecar exe -> UI bundle -> NSIS installer.
# Run from the repo root:  scripts\build.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

Write-Host "[1/3] Freezing Python sidecar (PyInstaller)..." -ForegroundColor Cyan
py -m PyInstaller sidecar.spec --noconfirm --clean
if (-not (Test-Path "dist\nitro-forge-sidecar.exe")) { throw "sidecar build failed" }

# The shell looks for the sidecar next to its own exe; Tauri bundles every
# file placed in src-tauri's binaries dir via the NSIS installer's app dir.
$shellRelease = "desktop\src-tauri\target\release"
New-Item -ItemType Directory -Force "$shellRelease" | Out-Null
Copy-Item "dist\nitro-forge-sidecar.exe" "$shellRelease\nitro-forge-sidecar.exe" -Force

Write-Host "[2/3] Building UI + shell + installer (tauri build)..." -ForegroundColor Cyan
Set-Location "$root\desktop"
npm run tauri build
Set-Location $root

Write-Host "[3/3] Done. Artifacts:" -ForegroundColor Green
Get-ChildItem "$shellRelease\bundle\nsis\*.exe" -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "  installer: $($_.FullName)" }
Write-Host "  sidecar:   $root\dist\nitro-forge-sidecar.exe"
Write-Host ""
Write-Host "The installer bundles the sidecar exe next to the app exe"
Write-Host "(tauri.conf.json > bundle > resources), so the installer is all"
Write-Host "users need. Run the sidecar build (step 1) before tauri build."
