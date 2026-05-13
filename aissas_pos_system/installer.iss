; Inno Setup 6 installer script for Aissa's Kitchenette POS System
; Build with:  build.bat   (or: ISCC.exe /DMyAppVersion=3.0 installer.iss)
;
; Install target: {localappdata}\Programs\AissasKitchenette
;   - App EXE and settings.json both live here
;   - Runtime data (DB, exports, receipts) auto-created in %APPDATA%\AissasPOS\
;
; ── BEFORE COMPILING ──────────────────────────────────────────────────────────
;   For Network Client installs, the server PC must share the AissasPOS data
;   folder as a network share named "AissasDB". Expected UNC path:
;     \\<server-IP>\AissasDB\data\pos.db
;   The installer writes this path into settings.json automatically.
;
; ── VERSION NOTE ──────────────────────────────────────────────────────────────
; MyAppVersion is normally overridden by build.bat via:
;   ISCC.exe /DMyAppVersion=X.Y.Z installer.iss
; The #ifndef guard below is the fallback for direct ISCC invocations.

#ifndef MyAppVersion
  #define MyAppVersion "3.0"
#endif

#define MyAppName          "Aissa's Kitchenette"
#define MyAppPublisher     "Aissa's Kitchenette"
#define MyAppExeName       "AissasKitchenette.exe"
#define MyAppIcon          "assets\logo.ico"
#define MyAppId            "A1552A01-CAFE-4B01-B001-AISSA1KITCH01"

[Setup]
AppId={{{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppComments=Point-of-sale system for Aissa's Kitchenette

; Installation directory — user-profile location keeps write access without issues
DefaultDirName={localappdata}\Programs\AissasKitchenette
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output
OutputDir=dist
OutputBaseFilename=AissasKitchenette_POS_v{#MyAppVersion}_Setup
SetupIconFile={#MyAppIcon}

; Installer appearance
WizardStyle=modern
DisableWelcomePage=no

; Branding (EXE Properties > Details)
VersionInfoVersion=3.0.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion=3.0.0.0

; Compression
Compression=lzma2/ultra64
SolidCompression=yes

; User-profile install directory — no system service, no elevation needed.
PrivilegesRequired=lowest
MinVersion=10.0

; Prevent duplicate installer instances
AppMutex={#MyAppName}-Installer-{#MyAppId}

; Close the running app before overwriting the EXE
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
; Only the EXE and settings.json live here.
; Runtime data in %APPDATA%\AissasPOS\ is auto-created on first launch.
Name: "{app}"

[Files]
; Main executable — one-file PyInstaller bundle
Source: "dist\AissasKitchenette.exe"; DestDir: "{app}"; DestName: "{#MyAppExeName}"; Flags: ignoreversion


[Icons]
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"; \
      IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; \
      IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
; ── Offer to launch the app immediately ───────────────────────────────────────
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName} now"; \
          Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Transient files written by the app next to the EXE.
; Runtime data in %APPDATA%\AissasPOS\ is intentionally preserved on uninstall
; so the database, receipts, and exports survive a reinstall or upgrade.
; settings.json is also kept so the role config survives reinstalls.
Type: filesandordirs; Name: "{app}\mpl_config"
Type: files;          Name: "{app}\app.log"

[Code]
// ── Shared wizard state ───────────────────────────────────────────────────────
var
  RolePage : TWizardPage;
  RbCashier: TNewRadioButton;
  RbOwner  : TNewRadioButton;
  LblIPHint: TNewStaticText;
  LblIPNote: TNewStaticText;
  EdtIP    : TNewEdit;


// ── IP field visibility ───────────────────────────────────────────────────────
procedure UpdateIPVisibility;
begin
  LblIPHint.Visible := RbOwner.Checked;
  LblIPNote.Visible := RbOwner.Checked;
  EdtIP.Visible     := RbOwner.Checked;
end;

procedure RbCashierClick(Sender: TObject);
begin
  UpdateIPVisibility;
end;

procedure RbOwnerClick(Sender: TObject);
begin
  UpdateIPVisibility;
end;


// ── Wizard setup ──────────────────────────────────────────────────────────────
procedure InitializeWizard;
var
  LblDesc: TNewStaticText;
  LblSub : TNewStaticText;
begin
  // Custom page appears after the directory selection page.
  RolePage := CreateCustomPage(wpSelectDir,
    'Select Device Role',
    'Choose how this PC connects to the Aissa''s Kitchenette database.');

  // Intro description
  LblDesc := TNewStaticText.Create(RolePage);
  LblDesc.Parent   := RolePage.Surface;
  LblDesc.Left     := 0;
  LblDesc.Top      := 0;
  LblDesc.Width    := RolePage.SurfaceWidth;
  LblDesc.WordWrap := True;
  LblDesc.AutoSize := True;
  LblDesc.Caption  :=
    'Select the role for this device. This determines whether the app uses a ' +
    'local database on this PC or connects to a shared database on the network.';

  // ── Radio: Cashier / Server PC ────────────────────────────────────────────
  RbCashier := TNewRadioButton.Create(RolePage);
  RbCashier.Parent  := RolePage.Surface;
  RbCashier.Left    := 0;
  RbCashier.Top     := 44;
  RbCashier.Width   := RolePage.SurfaceWidth;
  RbCashier.Caption := 'Cashier / Server PC  —  Local database (standalone)';
  RbCashier.Checked := True;
  RbCashier.OnClick := @RbCashierClick;

  LblSub := TNewStaticText.Create(RolePage);
  LblSub.Parent   := RolePage.Surface;
  LblSub.Left     := 16;
  LblSub.Top      := 64;
  LblSub.Width    := RolePage.SurfaceWidth - 16;
  LblSub.WordWrap := True;
  LblSub.AutoSize := True;
  LblSub.Caption  :=
    'The database is stored on this PC. Choose this for the main cashier ' +
    'station or any single-PC setup.';

  // ── Radio: Network Client ────────────────────────────────────────────────
  RbOwner := TNewRadioButton.Create(RolePage);
  RbOwner.Parent  := RolePage.Surface;
  RbOwner.Left    := 0;
  RbOwner.Top     := 110;
  RbOwner.Width   := RolePage.SurfaceWidth;
  RbOwner.Caption := 'Network Client  —  Network database (shared server)';
  RbOwner.OnClick := @RbOwnerClick;

  LblSub := TNewStaticText.Create(RolePage);
  LblSub.Parent   := RolePage.Surface;
  LblSub.Left     := 16;
  LblSub.Top      := 130;
  LblSub.Width    := RolePage.SurfaceWidth - 16;
  LblSub.WordWrap := True;
  LblSub.AutoSize := True;
  LblSub.Caption  :=
    'Reads from the shared database on the server PC over the local network.';

  // ── Server IP input (visible for Network Client only) ────────────────────
  LblIPHint := TNewStaticText.Create(RolePage);
  LblIPHint.Parent   := RolePage.Surface;
  LblIPHint.Left     := 0;
  LblIPHint.Top      := 178;
  LblIPHint.Width    := RolePage.SurfaceWidth;
  LblIPHint.AutoSize := True;
  LblIPHint.Caption  := 'Server PC IP address:';
  LblIPHint.Visible  := False;

  EdtIP := TNewEdit.Create(RolePage);
  EdtIP.Parent  := RolePage.Surface;
  EdtIP.Left    := 0;
  EdtIP.Top     := 197;
  EdtIP.Width   := 260;
  EdtIP.Text    := '192.168.1.100';
  EdtIP.Visible := False;

  LblIPNote := TNewStaticText.Create(RolePage);
  LblIPNote.Parent   := RolePage.Surface;
  LblIPNote.Left     := 0;
  LblIPNote.Top      := 227;
  LblIPNote.Width    := RolePage.SurfaceWidth;
  LblIPNote.WordWrap := True;
  LblIPNote.AutoSize := True;
  LblIPNote.Caption  :=
    'Use the LAN IP address (e.g. 192.168.1.100) of the PC that hosts the database.';
  LblIPNote.Visible := False;
end;


// ── Page validation ───────────────────────────────────────────────────────────
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = RolePage.ID then
  begin
    if RbOwner.Checked and (Trim(EdtIP.Text) = '') then
    begin
      MsgBox('Please enter the server PC IP address.',
             mbError, MB_OK);
      WizardForm.ActiveControl := EdtIP;
      Result := False;
    end;
  end;
end;


// ── Write settings.json after files are installed ─────────────────────────────
// config.py reads this file on startup to determine DB_MODE and NETWORK_DB_PATH.
procedure CurStepChanged(CurStep: TSetupStep);
var
  SettingsFile: String;
  DbMode      : String;
  NetworkPath : String;
  JsonNetPath : String;
  JsonContent : String;
begin
  if CurStep = ssPostInstall then
  begin
    SettingsFile := ExpandConstant('{app}\settings.json');

    if RbOwner.Checked then
    begin
      DbMode := 'network';
      // Build the UNC path expected by the server share setup.
      // Server PC must share %APPDATA%\AissasPOS\ as a share named "AissasDB".
      NetworkPath := '\\' + Trim(EdtIP.Text) + '\AissasDB\data\pos.db';
      // Each \ must be doubled for valid JSON string encoding.
      StringChange(NetworkPath, '\', '\\');
      JsonNetPath := NetworkPath;
    end
    else
    begin
      DbMode      := 'local';
      JsonNetPath := '';
    end;

    JsonContent :=
      '{' + #13#10 +
      '  "DB_MODE": "' + DbMode + '",' + #13#10 +
      '  "NETWORK_DB_PATH": "' + JsonNetPath + '"' + #13#10 +
      '}';

    SaveStringToFile(SettingsFile, JsonContent, False);
  end;
end;


// ── Upgrade detection ─────────────────────────────────────────────────────────
// Preserved from original installer — shows a notice on the Welcome page when
// overwriting an existing installation so users know their data is safe.
function IsUpgrade(): Boolean;
var
  AppDir: String;
begin
  AppDir := WizardDirValue();
  if AppDir = '' then
    Result := False
  else
    Result := FileExists(AppDir + '\{#MyAppExeName}');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = wpWelcome) and IsUpgrade() then
    WizardForm.WelcomeLabel2.Caption :=
      'This will upgrade Aissa''s Kitchenette to version {#MyAppVersion}.' + #13#10 +
      'Your database, receipts, exports, and product images will be fully preserved.' + #13#10#13#10 +
      WizardForm.WelcomeLabel2.Caption;
end;
