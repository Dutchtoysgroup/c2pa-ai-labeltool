# Bouwt de Windows-"app": downloadt c2patool.exe en maakt snelkoppelingen in het
# Startmenu en op het bureaublad. Herbruikbaar: draai dit opnieuw na wijzigingen.
# 'Continue' i.p.v. 'Stop': externe uitvoer mag het script niet laten crashen.
$ErrorActionPreference = "Continue"

$AppDir = (Resolve-Path "$PSScriptRoot\..").Path
$Bin = Join-Path $AppDir "bin"
New-Item -ItemType Directory -Force -Path $Bin | Out-Null

# --- c2patool.exe meebundelen (zelfde versie als de macOS-build) --------------
$Version = if ($env:C2PATOOL_VERSION) { $env:C2PATOOL_VERSION } else { "0.27.15" }
$Exe = Join-Path $Bin "c2patool.exe"
if (-not (Test-Path $Exe)) {
  $existing = Get-Command c2patool -ErrorAction SilentlyContinue
  if ($existing) {
    Copy-Item $existing.Source $Exe -Force
    Write-Host "-> c2patool overgenomen van PATH: $($existing.Source)"
  } else {
    try {
      $zip = Join-Path $env:TEMP "c2patool.zip"
      $tmp = Join-Path $env:TEMP "c2patool_extract"
      $url = "https://github.com/contentauth/c2pa-rs/releases/download/c2patool-v$Version/c2patool-v$Version-x86_64-pc-windows-msvc.zip"
      Write-Host "-> c2patool v$Version downloaden..."
      Invoke-WebRequest -UseBasicParsing $url -OutFile $zip
      Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
      Expand-Archive -Path $zip -DestinationPath $tmp -Force
      $found = Get-ChildItem -Recurse -Path $tmp -Filter "c2patool.exe" | Select-Object -First 1
      if ($found) { Copy-Item $found.FullName $Exe -Force; Write-Host "-> c2patool meegebundeld." }
      else { Write-Warning "c2patool.exe niet gevonden in de download." }
    } catch {
      Write-Warning "Download van c2patool mislukt: $($_.Exception.Message)"
      Write-Warning "Zet handmatig c2patool.exe in: $Bin  (zie README) en draai dit script opnieuw."
    }
  }
}

# --- Python-omgeving nu al opzetten (zodat de eerste start snel en zichtbaar is)
$venvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  $py = $null; $pyArgs = @()
  if (Get-Command py -ErrorAction SilentlyContinue)         { $py = "py";     $pyArgs = @("-3") }
  elseif (Get-Command python -ErrorAction SilentlyContinue) { $py = "python"; $pyArgs = @() }
  if ($py) {
    Write-Host "-> Python-omgeving opzetten (eenmalig, even geduld)..."
    & $py @pyArgs -m venv (Join-Path $AppDir ".venv")
    & $venvPy -m pip install -q --upgrade pip
    & $venvPy -m pip install -q -r (Join-Path $AppDir "requirements.txt")
    if (Test-Path $venvPy) { Write-Host "-> Python-omgeving klaar." }
    else { Write-Warning "Python-omgeving kon niet worden aangemaakt." }
  } else {
    Write-Warning "Python niet gevonden; de omgeving wordt bij de eerste start opgezet."
  }
}

# --- Snelkoppelingen (Startmenu + Bureaublad) ---------------------------------
# De snelkoppeling start via een klein VBS-bestand dat PowerShell volledig
# verborgen aanroept -> geen leeg terminalvenster meer.
$vbs = Join-Path $AppDir "winapp\launcher.vbs"
$icon = Join-Path $AppDir "winapp\AppIcon.ico"
$wsexe = Join-Path $env:SystemRoot "System32\wscript.exe"
$ws = New-Object -ComObject WScript.Shell
$targets = @(
  (Join-Path ([Environment]::GetFolderPath("Programs")) "C2PA AI-labeltool.lnk"),
  (Join-Path ([Environment]::GetFolderPath("Desktop"))  "C2PA AI-labeltool.lnk")
)
foreach ($t in $targets) {
  try {
    $lnk = $ws.CreateShortcut($t)
    $lnk.TargetPath = $wsexe
    $lnk.Arguments = "`"$vbs`""
    $lnk.WorkingDirectory = $AppDir
    $lnk.Description = "C2PA AI-labeltool"
    if (Test-Path $icon) { $lnk.IconLocation = $icon }
    $lnk.Save()
  } catch {
    Write-Warning "Kon snelkoppeling niet maken: $t ($($_.Exception.Message))"
  }
}

if (Test-Path $Exe) {
  Write-Host "`nKlaar: de app staat in het Startmenu en op het bureaublad."
} else {
  Write-Warning "`nSnelkoppelingen gemaakt, maar c2patool.exe ontbreekt in $Bin."
  Write-Warning "De app opent wel, maar de Start-knop blijft uit tot c2patool aanwezig is."
}
