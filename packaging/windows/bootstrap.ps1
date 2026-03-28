[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$InstallRoot,

    [string]$PythonVersion = "3.12",

    [string]$LogPath = $(Join-Path $InstallRoot "install.log")
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)

    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $LogPath -Value $line
    Write-Host $line
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    Write-Log ("Running: {0} {1}" -f $FilePath, ($Arguments -join " "))
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $quotedParts = @($FilePath) + $Arguments | ForEach-Object {
            if ($_ -match '[\s"]') {
                '"' + ($_ -replace '"', '\"') + '"'
            }
            else {
                $_
            }
        }
        $commandLine = (($quotedParts -join " ") + " 2>&1")
        & $env:ComSpec /d /c $commandLine | Tee-Object -FilePath $LogPath -Append
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    if ($exitCode -ne 0) {
        throw ("Command failed with exit code {0}: {1} {2}" -f $exitCode, $FilePath, ($Arguments -join " "))
    }
}

$InstallRoot = [System.IO.Path]::GetFullPath($InstallRoot)
$LogPath = [System.IO.Path]::GetFullPath($LogPath)
$logDir = Split-Path -Parent $LogPath
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

Set-Content -Path $LogPath -Value ("PyAMA bootstrap started at {0}" -f (Get-Date -Format "s"))

$uv = Join-Path $InstallRoot "tools\uv.exe"
if (-not (Test-Path -LiteralPath $uv)) {
    throw "Embedded uv.exe is missing from the installation payload."
}

$pythonInstallDir = Join-Path $InstallRoot "python"
$env:UV_PYTHON_INSTALL_DIR = $pythonInstallDir

function Resolve-ManagedPythonPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$InstallDir,

        [Parameter(Mandatory = $true)]
        [string]$RequestedVersion
    )

    for ($attempt = 0; $attempt -lt 10; $attempt++) {
        $directCandidates = @(
            (Join-Path $InstallDir ("cpython-{0}-windows-x86_64-none\python.exe" -f $RequestedVersion)),
            (Join-Path $InstallDir ("python-{0}\python.exe" -f $RequestedVersion))
        )

        foreach ($candidate in $directCandidates) {
            if (Test-Path -LiteralPath $candidate) {
                return $candidate
            }
        }

        $matchingInstall = Get-ChildItem -LiteralPath $InstallDir -Directory -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like ("cpython-{0}*-windows-x86_64-none" -f $RequestedVersion) } |
            Sort-Object Name -Descending |
            Select-Object -First 1

        if ($matchingInstall) {
            $pythonExe = Join-Path $matchingInstall.FullName "python.exe"
            if (Test-Path -LiteralPath $pythonExe) {
                return $pythonExe
            }
        }

        $recursiveMatch = Get-ChildItem -LiteralPath $InstallDir -Recurse -Filter python.exe -File -ErrorAction SilentlyContinue |
            Where-Object {
                $_.DirectoryName -like (Join-Path $InstallDir ("cpython-{0}*-windows-x86_64-none" -f $RequestedVersion))
            } |
            Sort-Object FullName |
            Select-Object -First 1

        if ($recursiveMatch) {
            return $recursiveMatch.FullName
        }

        Start-Sleep -Milliseconds 500
    }

    throw "Unable to locate the managed Python installation inside $InstallDir."
}

Push-Location $InstallRoot
try {
    Invoke-LoggedCommand -FilePath $uv -Arguments @(
        "python",
        "install",
        $PythonVersion,
        "--managed-python",
        "--install-dir",
        $pythonInstallDir,
        "--no-bin",
        "--no-registry"
    )

    $pythonPath = Resolve-ManagedPythonPath -InstallDir $pythonInstallDir -RequestedVersion $PythonVersion

    Write-Log ("Using Python interpreter: {0}" -f $pythonPath)

    $venvPath = Join-Path $InstallRoot ".venv"
    if (Test-Path -LiteralPath $venvPath) {
        Write-Log ("Removing existing virtual environment at {0}" -f $venvPath)
        Remove-Item -LiteralPath $venvPath -Recurse -Force
    }

    Invoke-LoggedCommand -FilePath $uv -Arguments @(
        "sync",
        "--project",
        $InstallRoot,
        "--frozen",
        "--no-dev",
        "--all-packages",
        "--no-editable",
        "--python",
        $pythonPath,
        "--compile-bytecode",
        "--link-mode",
        "copy"
    )

    foreach ($commandName in @("pyama-gui.exe")) {
        $commandPath = Join-Path $InstallRoot ".venv\Scripts\$commandName"
        if (-not (Test-Path -LiteralPath $commandPath)) {
            throw "Expected launcher was not created: $commandPath"
        }
    }

    Write-Log "PyAMA bootstrap completed successfully."
}
catch {
    Write-Log ("Bootstrap failed: {0}" -f $_)
    throw
}
finally {
    Pop-Location
}
