#define AppName "Goodneighbor Plague Radio DJ Writer"
#define AppExeName AppName + ".exe"
#ifndef AppVersion
  #define AppVersion "0.9.4"
#endif
#ifndef SourceDir
  #define SourceDir "dist\" + AppName
#endif
#ifndef BuildOutputDir
  #define BuildOutputDir "artifacts"
#endif
#ifdef AcceptanceBuild
  #define AppGuid "4B83CFD0-D246-4A56-B37E-FD594B26BF98"
  #define SetupBaseName "DJ-Writer-Acceptance-Setup"
#else
  #define AppGuid "B70EA637-F062-4B96-AEC0-A4664CA85A22"
  #define SetupBaseName "DJ-Writer-Setup-" + AppVersion
#endif

[Setup]
AppId={{{#AppGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Kaotick Jay / Plagued Mods
DefaultDirName={localappdata}\Programs\Goodneighbor DJ Writer
DefaultGroupName=Goodneighbor DJ Writer
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
SetupIconFile=assets\dj-writer.ico
UninstallDisplayIcon={app}\{#AppExeName}
LicenseFile=..\..\LICENSES\GPL-3.0.txt
OutputDir={#BuildOutputDir}
OutputBaseFilename={#SetupBaseName}
#ifdef AcceptanceBuild
Compression=none
SolidCompression=no
#else
Compression=lzma2
SolidCompression=yes
#endif
DiskSpanning=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion

#ifndef AcceptanceBuild
[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Icons]
Name: "{group}\Goodneighbor DJ Writer"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Goodneighbor DJ Writer"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
#endif

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch DJ Writer"; Flags: nowait postinstall skipifsilent

; Deliberately no UninstallDelete entries: user libraries, models and settings
; in ~/.goodneighbor_blues_dj are independent of the application installation.
