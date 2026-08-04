; Toolblox installer (beta).
;
; This is a bootstrapper, not a full offline installer: it downloads the
; actual application build from a GitHub release at install time instead of
; embedding it, so the installer itself stays small.
;
; MyAppVersion, DownloadURL, and DownloadSHA256 have no checked-in default -
; a stale or placeholder value here would compile fine and then fail (or
; silently point at the wrong release) only later, at install time, which
; is a much worse place to discover it. Compiling always requires passing
; all three via ISCC's own /D flag:
;   ISCC /DMyAppVersion=1.0.0 /DDownloadURL=https://... /DDownloadSHA256=... Toolblox.iss
; .github/workflows/release.yml does this automatically for a real release,
; computing DownloadSHA256 from the zip `python release/build.py` just
; produced. For a manual local compile, run that script first and pass its
; printed sha256 the same way.

#define MyAppName "Toolblox"
#ifndef MyAppVersion
  #error "MyAppVersion is not defined. Compile with /DMyAppVersion=<version>."
#endif
#define MyAppPublisher "BakedAleska"
#define MyAppExeName "Toolblox.exe"
#ifndef DownloadURL
  #error "DownloadURL is not defined. Compile with /DDownloadURL=<url>."
#endif
#define DownloadFileName "Toolblox-windows.zip"
#ifndef DownloadSHA256
  #error "DownloadSHA256 is not defined. Compile with /DDownloadSHA256=<sha256>."
#endif

[Setup]
AppId={{7E3F6C2D-6B7A-4A2E-9C3D-2C8F5B1E4A10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/BakedAleska/Toolblox
AppUpdatesURL=https://github.com/BakedAleska/Toolblox/releases
; NOTE: must not be {localappdata}\{#MyAppName} -- that path is the app's own
; DATA_DIR (toolblox/config.py), holding accounts.json, settings, and
; installed widgets. Installing there would collide with live user data.
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=ToolbloxSetup-{#MyAppVersion}
SetupIconFile=app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchiveExtraction=full
DisableWelcomePage=no
AppReadmeFile=https://github.com/BakedAleska/Toolblox
VersionInfoDescription=Toolblox installer (beta)
; Lets this same installer double as the updater toolblox/updater.py
; launches from inside a running app: if Toolblox.exe is still open when
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
