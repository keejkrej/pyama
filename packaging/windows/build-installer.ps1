[CmdletBinding()]
param(
    [string]$UvVersion = "0.10.4"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-PackageVersion {
    param([Parameter(Mandatory = $true)][string]$PyprojectPath)

    $match = Select-String -Path $PyprojectPath -Pattern '^\s*version\s*=\s*"([^"]+)"' | Select-Object -First 1
    if (-not $match) {
        throw "Could not find a version in $PyprojectPath"
    }

    return $match.Matches[0].Groups[1].Value
}

function Copy-Tree {
    param(
        [Parameter(Mandatory = $true)][string]$Source,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    Copy-Item -Path (Join-Path $Source "*") -Destination $Destination -Recurse -Force
}

function Get-IsccPath {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    $candidates = @(@(
        (Join-Path $env:USERPROFILE "scoop\shims\iscc.exe"),
        (Join-Path $env:USERPROFILE "scoop\apps\innosetup\current\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) })

    if ($candidates.Count -gt 0) {
        return $candidates[0]
    }

    throw "ISCC.exe was not found. Install Inno Setup 6 and ensure ISCC.exe is on PATH."
}

function New-UvExecutable {
    param(
        [Parameter(Mandatory = $true)][string]$Version,
        [Parameter(Mandatory = $true)][string]$Destination
    )

    $archiveUrl = "https://github.com/astral-sh/uv/releases/download/$Version/uv-x86_64-pc-windows-msvc.zip"
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ([System.Guid]::NewGuid().ToString("N"))
    $archivePath = Join-Path $tempRoot "uv.zip"
    $extractRoot = Join-Path $tempRoot "extract"

    New-Item -ItemType Directory -Path $extractRoot -Force | Out-Null
    try {
        Invoke-WebRequest -Uri $archiveUrl -OutFile $archivePath
        Expand-Archive -LiteralPath $archivePath -DestinationPath $extractRoot -Force

        $uvExe = Get-ChildItem -Path $extractRoot -Filter uv.exe -Recurse | Select-Object -First 1
        if (-not $uvExe) {
            throw "uv.exe was not found inside $archiveUrl"
        }

        New-Item -ItemType Directory -Path (Split-Path -Parent $Destination) -Force | Out-Null
        Copy-Item -LiteralPath $uvExe.FullName -Destination $Destination -Force
    }
    finally {
        if (Test-Path -LiteralPath $tempRoot) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$buildRoot = Join-Path $PSScriptRoot "build"
$stageRoot = Join-Path $buildRoot "stage"
$outputRoot = Join-Path $buildRoot "dist"
$issPath = Join-Path $PSScriptRoot "pyama.iss"
$isccPath = Get-IsccPath

$versions = @(
    (Get-PackageVersion -PyprojectPath (Join-Path $repoRoot "pyama\pyproject.toml")),
    (Get-PackageVersion -PyprojectPath (Join-Path $repoRoot "pyama-cli\pyproject.toml")),
    (Get-PackageVersion -PyprojectPath (Join-Path $repoRoot "pyama-gui\pyproject.toml"))
)

$uniqueVersions = @($versions | Sort-Object -Unique)
if ($uniqueVersions.Count -ne 1) {
    throw "Package versions must match before building an installer. Found: $($uniqueVersions -join ', ')"
}

$appVersion = $uniqueVersions[0]

if (Test-Path -LiteralPath $buildRoot) {
    Remove-Item -LiteralPath $buildRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $stageRoot, $outputRoot | Out-Null

Copy-Item -LiteralPath (Join-Path $repoRoot "pyproject.toml") -Destination (Join-Path $stageRoot "pyproject.toml")
Copy-Item -LiteralPath (Join-Path $repoRoot "uv.lock") -Destination (Join-Path $stageRoot "uv.lock")
Copy-Item -LiteralPath (Join-Path $repoRoot ".python-version") -Destination (Join-Path $stageRoot ".python-version")
Copy-Item -LiteralPath (Join-Path $repoRoot "README.md") -Destination (Join-Path $stageRoot "README.md")
New-Item -ItemType Directory -Path (Join-Path $stageRoot "tools") -Force | Out-Null

foreach ($packageName in @("pyama", "pyama-cli", "pyama-gui")) {
    $packageSource = Join-Path $repoRoot $packageName
    $packageDestination = Join-Path $stageRoot $packageName

    New-Item -ItemType Directory -Path $packageDestination -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $packageSource "pyproject.toml") -Destination (Join-Path $packageDestination "pyproject.toml")
    Copy-Tree -Source (Join-Path $packageSource "src") -Destination (Join-Path $packageDestination "src")
}

Copy-Tree -Source (Join-Path $PSScriptRoot "bin") -Destination (Join-Path $stageRoot "bin")
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "bootstrap.ps1") -Destination (Join-Path $stageRoot "tools\bootstrap.ps1")
New-UvExecutable -Version $UvVersion -Destination (Join-Path $stageRoot "tools\uv.exe")

& $isccPath `
    "/DAppVersion=$appVersion" `
    "/DStageDir=$stageRoot" `
    "/DOutputDir=$outputRoot" `
    $issPath

if ($LASTEXITCODE -ne 0) {
    throw "ISCC.exe failed with exit code $LASTEXITCODE"
}

Write-Host "Installer created in $outputRoot"
