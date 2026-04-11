; Inno Setup 6 installer script for Aissa's Kitchenette POS System
; Build with:  build.bat   (or ISCC.exe installer.iss directly)
;
; Install target: {localappdata}\Programs\AissasKitchenette
;   - No admin rights required (user-level install)
;   - Writable by the app  (database, receipts, exports go here)

#define MyAppName      "Aissa's Kitchenette"
#define MyAppVersion   "1.0.0-beta.2"
#define MyAppPublisher "Aissa's Kitchenette"
#define MyAppExeName   "AissasKitchenette.exe"
#define MyAppIcon      "assets\logo.ico"

[Setup]
AppId={{A1552A01-CAFE-4B01-B001-AISSA1KITCH01}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Point-of-sale system for Aissa's Kitchenette
DefaultDirName={localappdata}\Programs\AissasKitchenette
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=AissasKitchenette_Setup
SetupIconFile={#MyAppIcon}
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
MinVersion=10.0
; Allow the app to run immediately after install
CloseApplications=yes
RestartIfNeededByRun=no
; Version info embedded in setup EXE
VersionInfoVersion=1.0.0.2
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Dirs]
; Pre-create writable runtime directories so ZIP import works even before first launch.
; The app also creates these on startup (config.py), but having them ready at install
; time means a ZIP import immediately after install will find the data\ folder.
Name: "{app}\data"
Name: "{app}\product_images"
Name: "{app}\receipts"
Name: "{app}\exports"

[Files]
; Main executable (one-file EXE — everything bundled inside)
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}";   Filename: "{app}\{#MyAppExeName}"; \
      IconFilename: "{app}\{#MyAppExeName}"
; Desktop shortcut (optional)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
      IconFilename: "{app}\{#MyAppExeName}"; \
      Tasks: desktopicon
; Uninstall shortcut in Start Menu
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; Offer to launch app right after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; \
          Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove auto-created data folders when uninstalling
Type: filesandordirs; Name: "{app}\data"
Type: filesandordirs; Name: "{app}\receipts"
Type: filesandordirs; Name: "{app}\exports"
Type: filesandordirs; Name: "{app}\mpl_config"
Type: filesandordirs; Name: "{app}\product_images"
