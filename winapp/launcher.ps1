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

# Stap-voor-stap logje, zodat een probleem achteraf te zien is.
$Log = Join-Path $env:TEMP "c2pa-launcher.log"
function LogLine($m) {
  try { "$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))  $m" | Out-File -FilePath $Log -Append -Encoding utf8 } catch {}
}

function Test-Server {
  try { Invoke-WebRequest -UseBasicParsing -TimeoutSec 2 "$Url/api/status" | Out-Null; return $true }
  catch { return $false }
}

# Open de standaardbrowser op de tool. explorer.exe is de betrouwbaarste route
# (ShellExecute), met Start-Process als terugval.
function Open-App {
  LogLine "browser openen op $Url"
  try { Start-Process "explorer.exe" $Url; return } catch { LogLine "explorer faalde: $($_.Exception.Message)" }
  try { Start-Process $Url } catch { LogLine "Start-Process faalde: $($_.Exception.Message)" }
}

LogLine "=== launcher gestart (AppDir=$AppDir) ==="

# --- Auto-update vanaf GitHub (best-effort) -----------------------------------
$updated = $false
if ((Test-Path "$AppDir\.git") -and (Get-Command git -ErrorAction SilentlyContinue)) {
  $before = (git rev-parse HEAD) 2>$null
  $env:GIT_TERMINAL_PROMPT = "0"
  git pull --ff-only --quiet 2>$null
  $after = (git rev-parse HEAD) 2>$null
  if ($before -and $after -and ($before -ne $after)) {
    $updated = $true
    LogLine "nieuwe versie opgehaald ($before -> $after)"
    if (Test-Path "$AppDir\.venv\Scripts\python.exe") {
      & "$AppDir\.venv\Scripts\python.exe" -m pip install -q -r "$AppDir\requirements.txt" 2>$null
    }
  }
}

# --- Draait de server al? -----------------------------------------------------
if (Test-Server) {
  if ($updated) {
    LogLine "server draait al maar er is een update -> herstarten"
    Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
      Where-Object { $_.CommandLine -like "*$AppDir*" } |
      ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 1
  } else {
    LogLine "server draait al -> alleen browser openen"
    Open-App
    return
  }
}

# --- Eerste start: virtuele omgeving + dependencies ---------------------------
if (-not (Test-Path "$AppDir\.venv\Scripts\python.exe")) {
  LogLine "geen venv -> aanmaken"
  $py = $null; $pyArgs = @()
  if (Get-Command py -ErrorAction SilentlyContinue)      { $py = "py";     $pyArgs = @("-3") }
  elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python"; $pyArgs = @() }
  if (-not $py) {
    LogLine "Python 3 niet gevonden"
    [System.Windows.Forms.MessageBox]::Show(
      "Python 3 niet gevonden. Installeer Python via python.org en probeer opnieuw.",
      "C2PA AI-labeltool") | Out-Null
    return
  }
  & $py @pyArgs -m venv "$AppDir\.venv"
  & "$AppDir\.venv\Scripts\python.exe" -m pip install -q --upgrade pip
  & "$AppDir\.venv\Scripts\python.exe" -m pip install -q -r "$AppDir\requirements.txt"
}

# Ruim een eventueel vastgelopen eerdere server op: poort 8000 kan nog bezet zijn
# door een oud pythonw-proces dat niet meer op /api/status antwoordt, waardoor een
# nieuwe server niet kan binden ([Errno 10048]).
Get-CimInstance Win32_Process -Filter "Name = 'pythonw.exe'" |
  Where-Object { $_.CommandLine -like "*$AppDir*" } |
  ForEach-Object { LogLine "oude server stoppen (PID $($_.ProcessId))"; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 700

# --- Server op de achtergrond starten; wij openen de browser ------------------
LogLine "server starten"
$env:C2PA_NO_BROWSER = "1"
$outLog = Join-Path $env:TEMP "c2pa-ai-tool.out.log"
$errLog = Join-Path $env:TEMP "c2pa-ai-tool.err.log"
Start-Process -WindowStyle Hidden -FilePath "$AppDir\.venv\Scripts\pythonw.exe" `
  -ArgumentList "app.py" -WorkingDirectory $AppDir `
  -RedirectStandardOutput $outLog -RedirectStandardError $errLog

for ($i = 0; $i -lt 120; $i++) {
  if (Test-Server) { LogLine "server is op ($([int]($i*0.5))s) -> browser openen"; Open-App; return }
  Start-Sleep -Milliseconds 500
}
LogLine "server startte niet binnen 60s"
[System.Windows.Forms.MessageBox]::Show(
  "De server startte niet op tijd. Log: $errLog",
  "C2PA AI-labeltool") | Out-Null
