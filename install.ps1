# Installer voor "C2PA AI-labeltool" op Windows 11.
# Doet alles voor de collega: git/Python/gh regelen, GitHub-login (1x via
# browser), app ophalen, bouwen en starten. Daarna werkt de app zichzelf bij
# vanaf GitHub. Dubbelklik hiervoor op install.bat (of: rechtermuisklik ->
# "Uitvoeren met PowerShell").
$ErrorActionPreference = "Stop"

$Repo = "Dutchtoysgroup/c2pa-ai-labeltool"
$RepoUrl = "https://github.com/$Repo.git"
$Dest = Join-Path $env:USERPROFILE "c2pa-ai-tool"

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path", "User")
}
function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Die($msg) { Write-Host "`n$msg`n" -ForegroundColor Red; Read-Host "Enter om te sluiten"; exit 1 }

Write-Host "`n=== C2PA AI-labeltool - installatie ===`n"
Write-Host "Dit haalt de app op van GitHub, bouwt 'm en start 'm. Eenmalig.`n"

if (-not (Have "winget")) {
  Die "winget (App Installer) ontbreekt. Installeer 'App Installer' via de Microsoft Store en start deze installer opnieuw."
}

# 1) git
if (-not (Have "git")) {
  Write-Host "Git installeren..."
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
if (-not (Have "git")) { Die "Git kon niet worden geinstalleerd. Installeer git handmatig en probeer opnieuw." }

# 2) Python 3
if (-not (Have "python") -and -not (Have "py")) {
  Write-Host "Python installeren..."
  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
if (-not (Have "python") -and -not (Have "py")) { Die "Python kon niet worden geinstalleerd. Installeer Python via python.org en probeer opnieuw." }

# 3) GitHub CLI (voor een makkelijke login op de prive-repo)
if (-not (Have "gh")) {
  Write-Host "GitHub CLI installeren..."
  winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
if (-not (Have "gh")) { Die "GitHub CLI kon niet worden geinstalleerd. Probeer opnieuw of installeer 'gh' handmatig." }

# 4) inloggen bij GitHub (eenmalig, via de browser)
& gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Log even in bij GitHub - je browser opent zo. Volg de stappen."
  & gh auth login --hostname github.com --git-protocol https --web
  if ($LASTEXITCODE -ne 0) { Die "Inloggen bij GitHub is niet gelukt." }
}
& gh auth setup-git *> $null   # git gebruikt voortaan deze login (ook voor auto-update)

# 5) repo ophalen of bijwerken
if (Test-Path (Join-Path $Dest ".git")) {
  Write-Host "Bestaande installatie bijwerken..."
  git -C $Dest pull --ff-only
} else {
  Write-Host "App ophalen van GitHub..."
  git clone $RepoUrl $Dest
  if ($LASTEXITCODE -ne 0) { Die "Ophalen mislukt. Heb je toegang tot de repo? Vraag of je bent toegevoegd aan $Repo." }
}

# 6) app bouwen (downloadt zelf c2patool + maakt snelkoppelingen)
Write-Host "App bouwen..."
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dest "winapp\build_win_app.ps1")

# 7) starten
Write-Host "`nKlaar! De app staat in het Startmenu en op het bureaublad - en start nu."
Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $Dest 'winapp\launcher.ps1')`""

Write-Host "`nJe kunt dit venster sluiten. Voortaan open je de app via het Startmenu of het bureaublad."
Read-Host "Enter om te sluiten"
