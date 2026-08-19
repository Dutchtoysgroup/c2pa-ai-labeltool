# Launcher voor "C2PA AI-labeltool" op Windows.
# De snelkoppeling roept dit script aan: het haalt de nieuwste versie van GitHub
# op, start de lokale server (met de meegebundelde c2patool) en opent de tool in
# de browser. Faalt nooit hard: offline of geen toegang -> gewoon lokaal starten.
$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName System.Windows.Forms | Out-Null

$AppDir = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $AppDir

# Meegebundelde c2patool voorop in PATH.
$env:Path = "$AppDir\bin;$env:Path"
$Url = "http://localhost:8000"

function Test-Server {
  try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "$Url/api/status" | Out-Null; return $true }
  catch { return $false }
}

# --- Auto-update vanaf GitHub (best-effort) -----------------------------------
$updated = $false
if ((Test-Path "$AppDir\.git") -and (Get-Command git -ErrorAction SilentlyContinue)) {
  $before = (git rev-parse HEAD) 2>$null
  $env:GIT_TERMINAL_PROMPT = "0"
  git pull --ff-only --quiet 2>$null
  $after = (git rev-parse HEAD) 2>$null
  if ($before -and $after -and ($before -ne $after)) {
    $updated = $true
    if (Test-Path "$AppDir\.venv\Scripts\python.exe") {
      & "$AppDir\.venv\Scripts\python.exe" -m pip install -q -r "$AppDir\requirements.txt" 2>$null
    }
  }
}

# --- Draait de server al? -----------------------------------------------------
if (Test-Server) {
  if ($updated) {
    # Nieuwe versie opgehaald -> server herstarten zodat de nieuwe code laadt.
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
      Where-Object { $_.CommandLine -like "*$AppDir*" } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
  } else {
    Start-Process $Url
    return
  }
}

# --- Eerste start: virtuele omgeving + dependencies ---------------------------
if (-not (Test-Path "$AppDir\.venv\Scripts\python.exe")) {
  $py = $null; $pyArgs = @()
  if (Get-Command py -ErrorAction SilentlyContinue)      { $py = "py";     $pyArgs = @("-3") }
  elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python"; $pyArgs = @() }
  if (-not $py) {
    [System.Windows.Forms.MessageBox]::Show(
      "Python 3 niet gevonden. Installeer Python via python.org en probeer opnieuw.",
      "C2PA AI-labeltool") | Out-Null
    return
  }
  & $py @pyArgs -m venv "$AppDir\.venv"
  & "$AppDir\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
  & "$AppDir\.venv\Scripts\python.exe" -m pip install -q -r "$AppDir\requirements.txt"
}

# --- Server op de achtergrond starten; wij openen de browser ------------------
$env:C2PA_NO_BROWSER = "1"
$outLog = Join-Path $env:TEMP "c2pa-ai-tool.out.log"
$errLog = Join-Path $env:TEMP "c2pa-ai-tool.err.log"
Start-Process -WindowStyle Hidden -FilePath "$AppDir\.venv\Scripts\pythonw.exe" `
  -ArgumentList "app.py" -WorkingDirectory $AppDir `
  -RedirectStandardOutput $outLog -RedirectStandardError $errLog

for ($i = 0; $i -lt 60; $i++) {
  if (Test-Server) { Start-Process $Url; return }
  Start-Sleep -Milliseconds 500
}
[System.Windows.Forms.MessageBox]::Show(
  "De server startte niet op tijd. Log: $errLog",
  "C2PA AI-labeltool") | Out-Null
