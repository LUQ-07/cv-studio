<#  CV Studio - Windows build with PyInstaller. Run from the project root in PowerShell.

    .\build_exe.ps1            one-folder build  -> dist\CVStudio\CVStudio.exe   (recommended: starts fast, keeps Qt replaceable as the LGPL expects)
    .\build_exe.ps1 -OneFile   single exe        -> dist\CVStudio.exe             (slower start, some antivirus tools are suspicious of it)
#>
param([switch]$OneFile)
$ErrorActionPreference = "Stop"
py -3.12 -m pip install -r requirements-build.txt
py -3.12 tools\clean.py
if ($OneFile) {
  py -3.12 -m PyInstaller --noconfirm --clean --onefile --noconsole --name CVStudio `
    --icon "cvstudio\assets\cv-studio.ico" --add-data "cvstudio\assets;cvstudio\assets" `
    --hidden-import PySide6.QtPdf --exclude-module tkinter --exclude-module unittest run_app.py
  Write-Host "Built dist\CVStudio.exe"
} else {
  py -3.12 -m PyInstaller --noconfirm --clean "CV Studio.spec"
  Write-Host "Built dist\CVStudio\CVStudio.exe"
}
