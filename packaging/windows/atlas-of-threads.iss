#define AppName "Atlas of Threads"
#define AppVersion "0.1.0"
#define AppPublisher "MelaBuilt AI"
#define AppExeName "AtlasOfThreads.exe"

[Setup]
AppId={{0B5AD48B-9F79-47FB-90D1-3C164B7CEB39}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\Atlas of Threads
DefaultGroupName=Atlas of Threads
PrivilegesRequired=lowest
OutputDir=..\..\dist\windows-installer
OutputBaseFilename=AtlasOfThreadsSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
SetupIconFile=atlas-of-threads.ico
UninstallDisplayIcon={app}\{#AppExeName}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=force
RestartApplications=no

[Files]
Source: "..\..\dist\AtlasOfThreads.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Atlas of Threads"; Filename: "{app}\{#AppExeName}"
Name: "{userdesktop}\Atlas of Threads"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Open Atlas of Threads"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExeName}"; Flags: runhidden; RunOnceId: "StopAtlas"
