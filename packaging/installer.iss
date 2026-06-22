; Inno Setup script for DSI Redline.
; Build the app first (pyinstaller packaging/DSI_Redline.spec), then compile this
; with Inno Setup 6:  ISCC.exe packaging\installer.iss
; Produces dist_installer\DSI_Redline_Setup_<version>.exe

#define MyAppName "DSI Redline"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "DSI Innovations, LLC"
#define MyAppExeName "DSI Redline.exe"

[Setup]
AppId={{B5F4B0A2-3E2D-4C7A-9F1E-DS1REDLINE0001}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppCopyright=© DSI Innovations, LLC 2026
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist_installer
OutputBaseFilename=DSI_Redline_Setup_{#MyAppVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; The one-folder PyInstaller output (includes the bundled docs vault).
Source: "..\dist\DSI Redline\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
