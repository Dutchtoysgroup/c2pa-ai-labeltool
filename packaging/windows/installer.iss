; Inno Setup-script voor de Windows-installer van de C2PA AI-labeltool.
;
;   ISCC.exe /DAppVersion=2.0.0 packaging\windows\installer.iss
;
; Installeert per gebruiker (geen beheerdersrechten) in
; %LOCALAPPDATA%\Programs\C2PA AI-labeltool, met een snelkoppeling in het
; Startmenu en optioneel op het bureaublad. De app werkt zichzelf bij door deze
; setup stil te draaien (/VERYSILENT); de [Run]-regel start daarna de nieuwe
; versie, ook bij een stille installatie.

#ifndef AppVersion
  #error "Geef de versie mee: /DAppVersion=x.y.z"
#endif

#define AppName "C2PA AI-labeltool"
#define AppExe "C2PA AI-labeltool.exe"

[Setup]
; Vast houden: hieraan herkent Windows een eerdere installatie.
AppId={{B7D9CA14-D534-4129-959E-5ADA0A116E6C}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Dutch Toys Group
AppPublisherURL=https://dashboard-exit.com/labeltool
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=C2PA-AI-labeltool-{#AppVersion}-Windows-Setup
SetupIconFile=..\..\winapp\AppIcon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; Een draaiende server (dezelfde exe met --server) netjes laten sluiten.
CloseApplications=force
RestartApplications=no

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; Resten van een vorige versie weghalen, zodat er geen oude modules blijven.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\..\dist\C2PA AI-labeltool\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall
