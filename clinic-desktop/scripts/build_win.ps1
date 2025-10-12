Param(
    [string]$Python = "python"
)

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Root = Join-Path $Root ".."
$Dist = Join-Path $Root "dist"
$Venv = Join-Path $Root ".venv-build-win"

if (!(Test-Path $Venv)) {
    & $Python -m venv $Venv
}

. "$Venv/Scripts/Activate.ps1"

pip install -U pip
pip install -r "$Root/requirements.txt"
pip install pyinstaller==5.13.2

if (Test-Path $Dist) {
    Remove-Item $Dist -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $Dist | Out-Null

pyinstaller `
    --name Clinic `
    --noconfirm `
    --noconsole `
    --clean `
    --add-data "$Root/app/ui/qml;app/ui/qml" `
    --add-data "$Root/app/ui/assets;app/ui/assets" `
    --add-data "$Root/app/ui/styles;app/ui/styles" `
    --add-data "$Root/files;files" `
    --add-data "$Root/data;data" `
    --hidden-import "PySide6.QtQml" `
    --hidden-import "PySide6.QtQuickControls2" `
    --hidden-import "PySide6.QtSvg" `
    --hidden-import "weasyprint" `
    "$Root/app/main.py"

Write-Host "Exécutable Windows généré dans $Dist"
