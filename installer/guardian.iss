#define AppName "Guardian"
#define AppExe "..\dist\Guardian-installed.exe"
#define AppVersion GetVersionNumbersString(AppExe)
#ifdef GuardianTest
#define AppGuid "8468F74C-C3AB-4F87-B36A-A8FC0F467E14"
#else
#define AppGuid "FA8E8422-20CF-456E-80C5-C66C8D0BA1D4"
#endif

[Setup]
AppId={{{#AppGuid}}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Guardian
#ifdef GuardianTest
DefaultDirName={#GuardianTestDir}
#else
DefaultDirName={localappdata}\Programs\Guardian
#endif
DefaultGroupName=Guardian
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
MinVersion=10.0.22000
DisableWelcomePage=no
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
DisableReadyMemo=yes
WizardStyle=modern
WizardResizable=yes
SetupIconFile=..\assets\guardian.ico
UninstallDisplayIcon={app}\Guardian.exe
OutputDir=..\dist
OutputBaseFilename=Installer-Guardian
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[LangOptions]
DialogFontName=Segoe UI
DialogFontSize=14
WelcomeFontName=Segoe UI
WelcomeFontSize=22

[Messages]
WelcomeLabel1=Installer Guardian
WelcomeLabel2=Guardian sera installé sur cet ordinateur.
ClickNext=Cliquez sur Installer pour continuer.
ButtonNext=Installer
FinishedHeadingLabel=Guardian est installé
FinishedLabel=Guardian est installé ! Vous pouvez le retrouver sur le Bureau et dans le menu Démarrer.%n%nPour l'ajouter à la barre des tâches, ouvrez Guardian, puis faites un clic droit sur son icône dans la barre des tâches et choisissez « Épingler à la barre des tâches ».
InstallingLabel=Patientez pendant l'installation de Guardian.
ConfirmUninstall=Voulez-vous désinstaller Guardian ?%n%nSes réglages, sa liste de dossiers et son cache seront supprimés. Vos fichiers personnels et vos sauvegardes ne seront pas supprimés.

[Files]
Source: "{#AppExe}"; DestDir: "{app}"; DestName: "Guardian.exe"; Flags: ignoreversion

[Icons]
#ifdef GuardianTest
Name: "{app}\test-shortcuts\Bureau\Guardian"; Filename: "{app}\Guardian.exe"; WorkingDir: "{app}"
Name: "{app}\test-shortcuts\Démarrer\Guardian"; Filename: "{app}\Guardian.exe"; WorkingDir: "{app}"
#else
Name: "{userdesktop}\Guardian"; Filename: "{app}\Guardian.exe"; WorkingDir: "{app}"
Name: "{userprograms}\Guardian"; Filename: "{app}\Guardian.exe"; WorkingDir: "{app}"
#endif

[UninstallDelete]
Type: filesandordirs; Name: "{app}\GuardianData"
Type: filesandordirs; Name: "{localappdata}\Guardian\Installed"
Type: dirifempty; Name: "{localappdata}\Guardian"

[Code]
function GetSystemMetrics(nIndex: Integer): Integer;
  external 'GetSystemMetrics@user32.dll stdcall';

// L'assistant occupe une part fixe de la zone utile de l'écran réel
// (pixels physiques) ; fenêtre et polices suivent le même rapport.
procedure InitializeWizard;
var
  Ratio, MaxRatio: Double;
  WorkW, WorkH, NewW, NewH: Integer;
begin
  WorkW := GetSystemMetrics(16);
  WorkH := GetSystemMetrics(17);
#ifdef GuardianTestScreen
  WorkW := {#GuardianTestScreenW};
  WorkH := {#GuardianTestScreenH};
#endif
  if (WorkW <= 0) or (WorkH <= 0) then
    Exit;
  Ratio := (WorkH * 0.80) / WizardForm.Height;
  MaxRatio := (WorkW * 0.92) / WizardForm.Width;
  if Ratio > MaxRatio then
    Ratio := MaxRatio;
  if Ratio < 0.6 then
    Ratio := 0.6;
  if Ratio > 2.5 then
    Ratio := 2.5;
  NewW := Round(WizardForm.Width * Ratio);
  NewH := Round(WizardForm.Height * Ratio);
  WizardForm.Font.Size := Round(14 * Ratio);
  if WizardForm.Font.Size < 10 then
    WizardForm.Font.Size := 10;
  WizardForm.WelcomeLabel1.Font.Size := Round(22 * Ratio);
  WizardForm.FinishedHeadingLabel.Font.Size := Round(22 * Ratio);
  WizardForm.Width := NewW;
  WizardForm.Height := NewH;
  WizardForm.Left := (WorkW - NewW) div 2;
  WizardForm.Top := (WorkH - NewH) div 2;
end;

function ShortcutConflicts(const Path: String): Boolean;
var
  Shell, Shortcut: Variant;
begin
  Result := False;
  if FileExists(Path) then
  begin
    Shell := CreateOleObject('WScript.Shell');
    Shortcut := Shell.CreateShortcut(Path);
    Result := CompareText(Shortcut.TargetPath, ExpandConstant('{app}\Guardian.exe')) <> 0;
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  InstalledPath: String;
begin
  Result := '';
  if (FileExists(ExpandConstant('{app}\Guardian.exe')) or
      DirExists(ExpandConstant('{app}\GuardianData'))) and
    (not RegQueryStringValue(HKCU,
      'Software\Microsoft\Windows\CurrentVersion\Uninstall\{{#AppGuid}}_is1',
      'InstallLocation', InstalledPath) or
      (CompareText(RemoveBackslashUnlessRoot(InstalledPath),
        RemoveBackslashUnlessRoot(ExpandConstant('{app}'))) <> 0)) then
  begin
    Result := 'Des fichiers Guardian existent déjà dans le dossier prévu, mais ne correspondent pas à une installation Guardian reconnue. Ils ont été conservés.';
    Exit;
  end;
#ifndef GuardianTest
  if ShortcutConflicts(ExpandConstant('{userdesktop}\Guardian.lnk')) or
    ShortcutConflicts(ExpandConstant('{userprograms}\Guardian.lnk')) then
    Result := 'Un raccourci Guardian existe déjà et pointe vers un autre programme. Il a été conservé. Déplacez-le ou renommez-le avant de réessayer.';
#else
  if ShortcutConflicts(ExpandConstant('{app}\test-shortcuts\Bureau\Guardian.lnk')) or
    ShortcutConflicts(ExpandConstant('{app}\test-shortcuts\Démarrer\Guardian.lnk')) then
    Result := 'Un raccourci Guardian existe déjà et pointe vers un autre programme. Il a été conservé.';
#endif
end;
