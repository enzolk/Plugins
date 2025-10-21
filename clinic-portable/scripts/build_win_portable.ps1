Param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Join-Path $root ".."
Set-Location $projectRoot

$env:PYTHONPATH = $projectRoot
$distDir = Join-Path $projectRoot "dist"
if (-Not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
}

$pyinstallerArgs = @(
    "app/main.py",
    "--name", "ClinicPortable",
    "--windowed",
    "--noconfirm",
    "--add-data", "app/ui/qml;ui/qml",
    "--add-data", "app/ui/assets;ui/assets",
    "--add-data", "app/ui/styles;ui/styles",
    "--add-data", "files/pdf_templates;pdf_templates",
    "--add-data", "README.md;.",
    "--add-data", "LICENSE;."
)

if ($OneFile) {
    $pyinstallerArgs += "--onefile"
} else {
    $pyinstallerArgs += "--onedir"
}

pyinstaller @pyinstallerArgs
