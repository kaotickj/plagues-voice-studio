#define AppName "Plague's Voice Studio"
#ifndef AppVersion
  #define AppVersion "1.0.0rc1"
#endif
#define AppPublisher "Kaotick Jay"
#define AppExeName "PlaguesVoiceStudio030Experimental.exe"
#ifndef SourceDir
  #define SourceDir "dist\PlaguesVoiceStudio030Experimental"
#endif
#ifndef BuildOutputDir
  #define BuildOutputDir "dist-installer"
#endif
#ifdef AcceptanceBuild
  ; Isolate test installation registration and shortcuts from the real app.
  #define AppGuid "BF786FC2-C388-4F32-B3E2-EFD9D0CE488C"
  #define SetupBaseName "PVS-Acceptance-Setup"
#else
  #define AppGuid "2CC3087C-D88B-47D6-AF68-A949593B7BF2"
  #define SetupBaseName "PlaguesVoiceStudio-Setup-" + AppVersion
#endif

[Setup]
AppId={{{#AppGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
VersionInfoVersion=1.0.0.1
AppPublisher={#AppPublisher}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName}
VersionInfoProductName={#AppName}
VersionInfoCopyright=Copyright (c) 2026 Kaotick Jay
DefaultDirName={localappdata}\Programs\Plague's Voice Studio 0.3 Experimental
DefaultGroupName=Plague's Voice Studio 0.3
UninstallDisplayIcon={app}\{#AppExeName}
PrivilegesRequired=lowest
OutputDir={#BuildOutputDir}
OutputBaseFilename={#SetupBaseName}
#ifdef AcceptanceBuild
Compression=none
SolidCompression=no
#else
Compression=lzma2
SolidCompression=yes
#endif
; Inno Setup 6.5.2+ supports a single setup EXE up to nearly 4 GB.
; Slim release installers omit model weights; the application Model Manager downloads them later.\n; Fully bundled offline installers can be much larger and need separate hosting.
; Re-enable disk spanning only if the installer grows beyond that limit.
DiskSpanning=no
WizardStyle=modern
SetupIconFile=assets\plagues-voice-studio.ico
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
LicenseFile=LICENSES\GPL-3.0.txt

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

#ifndef AcceptanceBuild
[InstallDelete]
; Existing 0.3 installations may have shortcuts with the former preview label.
; Keep the same AppId and installation path so application data is preserved.
Type: files; Name: "{group}\\Plague's Voice Studio 0.3 Experimental.lnk"
Type: files; Name: "{autodesktop}\\Plague's Voice Studio 0.3 Experimental.lnk"

Type: files; Name: "{group}\Plague's Voice Studio 0.3.lnk"
Type: files; Name: "{autodesktop}\Plague's Voice Studio 0.3.lnk"

[Icons]
Name: "{group}\Plague's Voice Studio"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\Plague's Voice Studio"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon
#endif

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch Plague's Voice Studio"; Flags: nowait postinstall skipifsilent
