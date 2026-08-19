# Bouwt de Windows-"app": downloadt c2patool.exe en maakt snelkoppelingen in het
# Startmenu en op het bureaublad. Herbruikbaar: draai dit opnieuw na wijzigingen.
$ErrorActionPreference = "Stop"

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

# --- Snelkoppelingen (Startmenu + Bureaublad) ---------------------------------
$launcher = Join-Path $AppDir "winapp\launcher.ps1"
$icon = Join-Path $AppDir "winapp\AppIcon.ico"
$psexe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$ws = New-Object -ComObject WScript.Shell
$targets = @(
  (Join-Path ([Environment]::GetFolderPath("Programs")) "C2PA AI-labeltool.lnk"),
  (Join-Path ([Environment]::GetFolderPath("Desktop"))  "C2PA AI-labeltool.lnk")
)
foreach ($t in $targets) {
  $lnk = $ws.CreateShortcut($t)
  $lnk.TargetPath = $psexe
  $lnk.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$launcher`""
  $lnk.WorkingDirectory = $AppDir
  $lnk.Description = "C2PA AI-labeltool"
  if (Test-Path $icon) { $lnk.IconLocation = $icon }
  $lnk.Save()
}

Write-Host "`nKlaar: de app staat in het Startmenu en op het bureaublad."
