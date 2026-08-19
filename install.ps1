# Installer voor "C2PA AI-labeltool" op Windows 11.
# Doet alles voor de collega: git/Python/gh regelen, GitHub-login (1x via
# browser), app ophalen, bouwen en starten. Daarna werkt de app zichzelf bij
# vanaf GitHub. Dubbelklik hiervoor op install.bat (of: rechtermuisklik ->
# "Uitvoeren met PowerShell").

# BELANGRIJK: geen '$ErrorActionPreference = Stop'. Externe programma's (gh, git,
# winget) schrijven info naar stderr; onder 'Stop' zou Windows PowerShell 5.1 dat
# als fatale fout zien en meteen afbreken. We controleren zelf $LASTEXITCODE.
$ErrorActionPreference = "Continue"
$PSNativeCommandUseErrorActionPreference = $false   # PS 7+ safety; genegeerd op 5.1

# Vangnet: elke onverwachte terminating error netjes tonen i.p.v. venster sluiten.
trap { Write-Host "`nOnverwachte fout: $($_.Exception.Message)" -ForegroundColor Red; Read-Host "Enter om te sluiten"; exit 1 }

$Repo = "Dutchtoysgroup/c2pa-ai-labeltool"
$RepoUrl = "https://github.com/$Repo.git"
$Dest = Join-Path $env:USERPROFILE "c2pa-ai-tool"

function Refresh-Path {
  $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
              [Environment]::GetEnvironmentVariable("Path", "User")
}
function Have($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Fail($msg) { Write-Host "`n$msg`n" -ForegroundColor Red; Read-Host "Enter om te sluiten"; exit 1 }

Write-Host "`n=== C2PA AI-labeltool - installatie ===`n"
Write-Host "Dit haalt de app op van GitHub, bouwt 'm en start 'm. Eenmalig.`n"

if (-not (Have "winget")) {
  Fail "winget (App Installer) ontbreekt. Installeer 'App Installer' via de Microsoft Store en start deze installer opnieuw."
}

# 1) git
if (-not (Have "git")) {
  Write-Host "Git installeren..."
  winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
if (-not (Have "git")) { Fail "Git kon niet worden geinstalleerd. Installeer git handmatig en probeer opnieuw." }

# 2) Python 3
if (-not (Have "python") -and -not (Have "py")) {
  Write-Host "Python installeren..."
  winget install --id Python.Python.3.12 -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
if (-not (Have "python") -and -not (Have "py")) { Fail "Python kon niet worden geinstalleerd. Installeer Python via python.org en probeer opnieuw." }

# 3) GitHub CLI (voor een makkelijke login op de prive-repo)
if (-not (Have "gh")) {
  Write-Host "GitHub CLI installeren..."
  winget install --id GitHub.cli -e --source winget --accept-package-agreements --accept-source-agreements
  Refresh-Path
}
if (-not (Have "gh")) { Fail "GitHub CLI kon niet worden geinstalleerd. Probeer opnieuw of installeer 'gh' handmatig." }

# 4) inloggen bij GitHub (eenmalig, via de browser)
Write-Host "Controleren of je al bij GitHub bent ingelogd..."
gh auth status 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Log even in bij GitHub - je browser opent zo. Volg de stappen."
  gh auth login --hostname github.com --git-protocol https --web
  if ($LASTEXITCODE -ne 0) { Fail "Inloggen bij GitHub is niet gelukt. Start de installer opnieuw en probeer nog een keer." }
}
gh auth setup-git 2>&1 | Out-Null   # git gebruikt voortaan deze login (ook voor auto-update)

# 5) repo ophalen of bijwerken
if (Test-Path (Join-Path $Dest ".git")) {
  Write-Host "Bestaande installatie bijwerken..."
  # Uitvoer opvangen i.p.v. tonen: git schrijft voortgang naar stderr, wat
  # PowerShell anders (onterecht) rood weergeeft. Alleen bij een echte fout tonen.
  $gitOut = git -C $Dest pull --ff-only --quiet 2>&1
  if ($LASTEXITCODE -ne 0) { $gitOut | ForEach-Object { Write-Host $_ }; Fail "Bijwerken mislukt." }
} else {
  Write-Host "App ophalen van GitHub..."
  $gitOut = git clone --quiet $RepoUrl $Dest 2>&1
  if ($LASTEXITCODE -ne 0) { $gitOut | ForEach-Object { Write-Host $_ }; Fail "Ophalen mislukt. Heb je toegang tot de repo? Vraag of je bent toegevoegd aan $Repo." }
}

# 6) app bouwen (downloadt zelf c2patool + maakt snelkoppelingen)
Write-Host "`nApp bouwen..."
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Dest "winapp\build_win_app.ps1")

# 7) starten
Write-Host "`nKlaar! De app staat in het Startmenu en op het bureaublad - en start nu."
Start-Process -FilePath "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" `
  -ArgumentList "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$(Join-Path $Dest 'winapp\launcher.ps1')`""

Write-Host "`nJe kunt dit venster sluiten. Voortaan open je de app via het Startmenu of het bureaublad."
Read-Host "Enter om te sluiten"
