; Inno Setup 6 installer script for Aissa's Kitchenette POS System
; Build with:  build.bat   (or: ISCC.exe /DMyAppVersion=2.0.0 installer.iss)
;
; Install target: {localappdata}\Programs\AissasKitchenette
;   - No admin rights required (user-level install)
;   - EXE is read-only here; all writable data goes to %APPDATA%\AissasPOS\
;     (database, exports, receipts, product_images — auto-created on first launch)
;
; ── VERSION NOTE ──────────────────────────────────────────────────────────────
; MyAppVersion is normally overridden by build.bat via:
;   ISCC.exe /DMyAppVersion=X.Y.Z installer.iss
; The #ifndef guard below is the fallback for direct ISCC invocations.
; When bumping the release version, update it in build.bat (APP_VERSION) and
; version_info.txt — installer.iss picks it up from build.bat automatically.

#ifndef MyAppVersion
  #define MyAppVersion "2.0.0"
#endif

#define MyAppName      "Aissa's Kitchenette"
#define MyAppPublisher "Aissa's Kitchenette"
#define MyAppExeName   "AissasKitchenette.exe"
#define MyAppIcon      "assets\logo.ico"
#define MyAppId        "A1552A01-CAFE-4B01-B001-AISSA1KITCH01"

[Setup]
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Point-of-sale system for Aissa's Kitchenette

; Installation directory — user-level, no elevation required
DefaultDirName={localappdata}\Programs\AissasKitchenette
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output
OutputDir=dist
OutputBaseFilename=AissasKitchenette_v{#MyAppVersion}_Setup
SetupIconFile={#MyAppIcon}

; Installer appearance
WizardStyle=modern
DisableWelcomePage=no

; Branding in EXE Properties > Details
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}.0

; Compression
Compression=lzma2/ultra64
SolidCompression=yes

; Privileges — user-level install (no UAC prompt)
PrivilegesRequired=lowest
MinVersion=10.0

; Prevent duplicate installer instances running simultaneously
AppMutex={#MyAppName}-Installer-{#MyAppId}

; Close the running app before overwriting the EXE, then offer restart
CloseApplications=yes
RestartIfNeededByRun=no

; Uninstall display
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName} {#MyAppVersion}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[Dirs]
; Installation directory holds only the read-only EXE.
; All writable runtime data (DB, exports, receipts, product_images)
; lives in %APPDATA%\AissasPOS\ and is auto-created by config.py.
Name: "{app}"

[Files]
; Main executable — one-file PyInstaller bundle (everything inside)
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}";             Filename: "{app}\{#MyAppExeName}"; \
      IconFilename: "{app}\{#MyAppExeName}"
; Desktop shortcut (optional task)
Name: "{autodesktop}\{#MyAppName}";       Filename: "{app}\{#MyAppExeName}"; \
      IconFilename: "{app}\{#MyAppExeName}"; \
      Tasks: desktopicon
; Uninstall entry in Start Menu
Name: "{group}\Uninstall {#MyAppName}";   Filename: "{uninstallexe}"

[Run]
; Offer to launch immediately after install
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; \
          Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove transient files written next to the EXE during normal use.
; NOTE: User data in %APPDATA%\AissasPOS\ (database, exports, receipts,
;       product_images) is intentionally NOT deleted on uninstall so it
;       survives a reinstall or version upgrade.
Type: filesandordirs; Name: "{app}\mpl_config"
Type: files;          Name: "{app}\app.log"

[Code]
// ── Upgrade detection ────────────────────────────────────────────────────────
// Check whether a previous installation already exists at {app}.
// Used to customise the Welcome page message for upgrade scenarios.

function IsUpgrade(): Boolean;
var
  AppDir: String;
begin
  // {app} is not initialized until the directory page is confirmed, so use
  // WizardDirValue() which is safe to call at any point in the wizard.
  AppDir := WizardDirValue();
  if AppDir = '' then
    Result := False
  else
    Result := FileExists(AppDir + '\{#MyAppExeName}');
end;

// Prepend an upgrade notice to the Welcome page when overwriting an existing
// installation, reassuring users that their data is preserved.
procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpWelcome) and IsUpgrade() then
    WizardForm.WelcomeLabel2.Caption :=
      'This will upgrade Aissa''s Kitchenette to version {#MyAppVersion}.' + #13#10 +
      'Your database, receipts, exports, and product images will be fully preserved.' + #13#10#13#10 +
      WizardForm.WelcomeLabel2.Caption;
end;
