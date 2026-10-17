#define AppName "Plague's Voice Studio 0.3"
#define AppVersion "0.3.0-rc1"
#define AppPublisher "Kaotick Jay"
#define AppExeName "PlaguesVoiceStudio030Experimental.exe"

[Setup]
AppId={{2CC3087C-D88B-47D6-AF68-A949593B7BF2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName}
VersionInfoProductName={#AppName}
VersionInfoCopyright=Copyright (c) 2026 Kaotick Jay
DefaultDirName={localappdata}\Programs\Plague's Voice Studio 0.3 Experimental
DefaultGroupName={#AppName}
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest
OutputDir=dist-installer
OutputBaseFilename=PlaguesVoiceStudio030Experimental-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
; Inno Setup 6.5.2+ supports a single setup EXE up to nearly 4 GB.
; This ~3 GB Nano installer must NEVER request additional media.
; Re-enable disk spanning only if the installer grows beyond that limit.
DiskSpanning=no
WizardStyle=modern
SetupIconFile=assets\plagues-voice-studio.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=LICENSE

[Files]
Source: "dist\PlaguesVoiceStudio030Experimental\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
; Existing 0.3 installations may have shortcuts with the former preview label.
; Keep the same AppId and installation path so application data is preserved.
Type: files; Name: "{group}\\Plague's Voice Studio 0.3 Experimental.lnk"
Type: files; Name: "{autodesktop}\\Plague's Voice Studio 0.3 Experimental.lnk"

[Icons]
Name: "{group}\Plague's Voice Studio 0.3"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Plague's Voice Studio 0.3"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Plague's Voice Studio"; Flags: nowait postinstall skipifsilent
