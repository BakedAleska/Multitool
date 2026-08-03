; Multitool installer (beta).
;
; This is a bootstrapper, not a full offline installer: it downloads the
; actual application build from a GitHub release at install time instead of
; embedding it, so the installer itself stays small. Update AppVersion,
; DownloadURL, and DownloadSHA256 for each new release.

#define MyAppName "Multitool"
#define MyAppVersion "0.1.0-beta"
#define MyAppPublisher "BakedAleska"
#define MyAppExeName "Multitool.exe"
#define DownloadURL "https://github.com/BakedAleska/Multitool/releases/download/v0.1.0-beta/Multitool-0.1.0-beta-windows.zip"
#define DownloadFileName "Multitool-windows.zip"
#define DownloadSHA256 "ec4d8a534837505a3d9e5394901d40cd8576ff660cc25fdd47866a90853092e3"

[Setup]
AppId={{7E3F6C2D-6B7A-4A2E-9C3D-2C8F5B1E4A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/BakedAleska/Multitool
AppUpdatesURL=https://github.com/BakedAleska/Multitool/releases
; NOTE: must not be {localappdata}\{#MyAppName} -- that path is the app's own
; DATA_DIR (multitool/config.py), holding accounts.json, settings, and
; installed widgets. Installing there would collide with live user data.
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=MultitoolSetup-{#MyAppVersion}
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchiveExtraction=full
DisableWelcomePage=no
AppReadmeFile=https://github.com/BakedAleska/Multitool
VersionInfoDescription=Multitool installer (beta)
; Lets this same installer double as the updater multitool/updater.py
; launches from inside a running app: if Multitool.exe is still open when
; its own update relaunches this installer, close it automatically instead
; of blocking on a "file in use" prompt, then start it back up afterward.
CloseApplications=yes
RestartApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{tmp}\{#DownloadFileName}"; DestDir: "{app}"; Flags: external extractarchive recursesubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  DownloadPage: TDownloadWizardPage;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Error: String;
begin
  if CurPageID = wpReady then begin
    DownloadPage.Clear;
    DownloadPage.Add('{#DownloadURL}', '{#DownloadFileName}', '{#DownloadSHA256}');
    DownloadPage.Show;
    try
      try
        DownloadPage.Download;
        Result := True;
      except
        if DownloadPage.AbortedByUser then
          Log('Aborted by user.')
        else begin
          Error := Format('%s: %s', [DownloadPage.LastBaseNameOrUrl, GetExceptionMessage]);
          SuppressibleMsgBox(AddPeriod(Error), mbCriticalError, MB_OK, IDOK);
        end;
        Result := False;
      end;
    finally
      DownloadPage.Hide;
    end;
  end else
    Result := True;
end;
