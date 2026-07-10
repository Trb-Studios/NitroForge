# Opens the Nitro Forge website (live if reachable, local copy otherwise).
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\open-website.ps1
$live  = "https://trb-studios.github.io/NitroForge/"
$local = Join-Path (Split-Path -Parent $PSScriptRoot) "website\index.html"

try {
    Invoke-WebRequest $live -Method Head -UseBasicParsing -TimeoutSec 5 | Out-Null
    Start-Process $live
    Write-Host "Opened live site: $live" -ForegroundColor Cyan
} catch {
    Write-Host "Live site unreachable - opening local copy" -ForegroundColor Yellow
    Start-Process $local
}
