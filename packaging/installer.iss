; Inno Setup script — shows the ECIT EULA as an accept screen before installing.
#define AppName "ECIT Admin Console"
#define AppVersion "0.1.0"

[Setup]
AppId={{7585A021-C631-44BC-8996-70CA062E1878}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=ECIT IT Services
AppPublisherURL=https://ecit.co.il
AppSupportURL=mailto:info@ecit.co.il
DefaultDirName={autopf}\ECIT Admin Console
DefaultGroupName=ECIT
LicenseFile=..\resources\EULA.txt
OutputDir=..\dist
OutputBaseFilename=ECIT-Admin-Console-{#AppVersion}-setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
Source: "..\dist\ECIT Admin Console\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\ECIT Admin Console"; Filename: "{app}\ECIT Admin Console.exe"
Name: "{autodesktop}\ECIT Admin Console"; Filename: "{app}\ECIT Admin Console.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"

[Run]
Filename: "{app}\ECIT Admin Console.exe"; Description: "Launch ECIT Admin Console"; Flags: postinstall nowait skipifsilent
