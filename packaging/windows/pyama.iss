#define MyAppName "PyAMA"

#ifndef AppVersion
  #define AppVersion "0.0.0-dev"
#endif

#ifndef StageDir
  #error StageDir must be defined by the build script.
#endif

#ifndef OutputDir
  #define OutputDir AddBackslash(SourcePath) + "build\dist"
#endif

[Setup]
AppId={{0A15F5A7-D8D0-4A90-B331-9D5A48B5F7E8}
AppName={#MyAppName}
AppVersion={#AppVersion}
AppPublisher=PyAMA Team
DefaultDirName={localappdata}\Programs\PyAMA
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\.venv\Scripts\pyama-gui.exe
OutputDir={#OutputDir}
OutputBaseFilename=PyAMA-Setup-{#AppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
SetupLogging=yes
ChangesEnvironment=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PyAMA GUI"; Filename: "{app}\.venv\Scripts\pyama-gui.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\PyAMA GUI"; Filename: "{app}\.venv\Scripts\pyama-gui.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Code]
const
  PythonVersion = '3.12';

function NormalizePathEntry(Value: string): string;
begin
  Result := Trim(Value);
  StringChangeEx(Result, '/', '\', True);
  while (Length(Result) > 3) and (Result[Length(Result)] = '\') do
    Delete(Result, Length(Result), 1);
  Result := Lowercase(Result);
end;

function PathEntryExists(PathValue: string; Entry: string): Boolean;
var
  Current: string;
  Index: Integer;
begin
  Result := False;
  Entry := NormalizePathEntry(Entry);
  Current := '';

  for Index := 1 to Length(PathValue) do
  begin
    if PathValue[Index] = ';' then
    begin
      if NormalizePathEntry(Current) = Entry then
      begin
        Result := True;
        Exit;
      end;
      Current := '';
    end
    else
      Current := Current + PathValue[Index];
  end;

  if NormalizePathEntry(Current) = Entry then
    Result := True;
end;

function AppendPathEntry(PathValue: string; Entry: string): string;
begin
  if Trim(PathValue) = '' then
    Result := Entry
  else if PathEntryExists(PathValue, Entry) then
    Result := PathValue
  else
    Result := PathValue + ';' + Entry;
end;

function RemovePathEntry(PathValue: string; Entry: string): string;
var
  Current: string;
  Index: Integer;
begin
  Result := '';
  Current := '';
  Entry := NormalizePathEntry(Entry);

  for Index := 1 to Length(PathValue) do
  begin
    if PathValue[Index] = ';' then
    begin
      if (Trim(Current) <> '') and (NormalizePathEntry(Current) <> Entry) then
      begin
        if Result <> '' then
          Result := Result + ';';
        Result := Result + Current;
      end;
      Current := '';
    end
    else
      Current := Current + PathValue[Index];
  end;

  if (Trim(Current) <> '') and (NormalizePathEntry(Current) <> Entry) then
  begin
    if Result <> '' then
      Result := Result + ';';
    Result := Result + Current;
  end;
end;

procedure UpdateUserPath(AddEntry: Boolean);
var
  BinDir: string;
  CurrentPath: string;
  NewPath: string;
begin
  BinDir := ExpandConstant('{app}\bin');
  CurrentPath := '';
  RegQueryStringValue(HKCU, 'Environment', 'Path', CurrentPath);

  if AddEntry then
    NewPath := AppendPathEntry(CurrentPath, BinDir)
  else
    NewPath := RemovePathEntry(CurrentPath, BinDir);

  if NewPath = CurrentPath then
    Exit;

  if NewPath = '' then
    RegDeleteValue(HKCU, 'Environment', 'Path')
  else
    RegWriteExpandStringValue(HKCU, 'Environment', 'Path', NewPath);
end;

procedure RunBootstrap;
var
  ResultCode: Integer;
  Params: string;
  LogPath: string;
begin
  LogPath := ExpandConstant('{app}\install.log');
  Params :=
    '-ExecutionPolicy Bypass -NoProfile -File ' + AddQuotes(ExpandConstant('{app}\tools\bootstrap.ps1')) +
    ' -InstallRoot ' + AddQuotes(ExpandConstant('{app}')) +
    ' -PythonVersion ' + AddQuotes(PythonVersion) +
    ' -LogPath ' + AddQuotes(LogPath);

  if not Exec(
    ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoLogo ' + Params,
    '',
    SW_SHOW,
    ewWaitUntilTerminated,
    ResultCode
  ) then
    RaiseException('Unable to launch the PyAMA bootstrap script.');

  if ResultCode <> 0 then
    RaiseException(Format('PyAMA setup could not finish configuring the environment. See "%s" for details.', [LogPath]));
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    RunBootstrap;
    UpdateUserPath(True);
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    UpdateUserPath(False);
end;
