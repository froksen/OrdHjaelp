; Inno Setup: installer til Ordhjælp på Windows.
; Bygges af build-installer.ps1, som giver versionen med: ISCC /DAppVersion=0.3.0 ordhjaelp.iss
;
; Installeres for den aktuelle bruger (kræver ikke administrator), ligesom Ordhjælps
; autostart, indstillinger og sprogmodeller også er pr. bruger.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6E0C5B7A-3F0D-4C55-9C1B-0D5A2F7E9B41}
AppName=Ordhjælp
AppVersion={#AppVersion}
AppVerName=Ordhjælp {#AppVersion}
AppPublisher=Ole Frandsen
AppPublisherURL=https://github.com/froksen/OrdHjaelp
AppSupportURL=https://github.com/froksen/OrdHjaelp/issues
DefaultDirName={autopf}\Ordhjaelp
DefaultGroupName=Ordhjælp
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE
OutputDir=..\..\dist
OutputBaseFilename=Ordhjaelp-{#AppVersion}-Setup
SetupIconFile=build\ordhjaelp.ico
UninstallDisplayIcon={app}\Ordhjaelp.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "danish"; MessagesFile: "compiler:Languages\Danish.isl"

[Tasks]
Name: "autostart"; Description: "Start Ordhjælp automatisk, når der logges ind"
Name: "desktopicon"; Description: "Genvej på skrivebordet"; Flags: unchecked

[Files]
Source: "..\..\dist\Ordhjaelp\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Ordhjælp"; Filename: "{app}\Ordhjaelp.exe"; Comment: "Dansk læse- og skrivehjælp"
Name: "{autodesktop}\Ordhjælp"; Filename: "{app}\Ordhjaelp.exe"; Tasks: desktopicon

[Registry]
; Samme værdi som Ordhjælps egen indstilling "Start Ordhjælp automatisk", så de følges ad
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "Ordhjaelp"; ValueData: """{app}\Ordhjaelp.exe"" start"; \
  Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\Ordhjaelp.exe"; Description: "Start Ordhjælp nu"; \
  Flags: nowait postinstall skipifsilent

[UninstallRun]
; Luk Ordhjælp pænt, før filerne fjernes
Filename: "{app}\Ordhjaelp.exe"; Parameters: "afslut"; Flags: runhidden waituntilterminated; \
  RunOnceId: "LukOrdhjaelp"

[Code]
// Autostart-værdien fjernes også, hvis den blev slået til inde i Ordhjælp
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Ordhjaelp');
end;
