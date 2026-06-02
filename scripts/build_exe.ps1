# Build a standalone Windows executable with PyInstaller.
#
# Works no matter where you run it from — paths are resolved relative to this
# script's location (the repo root is its parent folder).
#
# Usage:
#   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1            # one-dir (recommended)
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1 -OneFile   # single .exe
#
# IMPORTANT: the runnable output is in dist\, NOT build\ (build\ holds
# intermediate files only and has no python3xx.dll).
#   one-dir : dist\XVALite\XVALite.exe   (ship the whole XVALite folder, ~196 MB)
#   one-file: dist\XVALite.exe           (single file; slower first start)
#
# Drop --windowed to keep a console window for debugging.

param([switch]$OneFile)

$ErrorActionPreference = "Stop"

# Resolve repo root from this script's location and work from there.
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$py = Join-Path $repo ".venv\Scripts\python.exe"

if (-not (Test-Path $py)) { throw "Python venv not found at $py" }

# Make sure the icon exists.
if (-not (Test-Path "$repo\assets\icon.ico")) {
    & $py "$repo\scripts\make_icon.py"
}

$pyiArgs = @(
    "--noconfirm", "--clean", "--windowed", "--name", "XVALite",
    "--paths", "src",
    "--icon", "assets\icon.ico",
    "--add-data", "assets\icon.ico;assets",
    "--collect-all", "soundfile",
    "--collect-all", "sounddevice",
    "--collect-all", "parselmouth"
)
if ($OneFile) { $pyiArgs += "--onefile" }
$pyiArgs += "xvalite_app.py"

& $py -m PyInstaller @pyiArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE"
}

Write-Host ""
if ($OneFile) {
    Write-Host "Build complete. Run: dist\XVALite.exe"
} else {
    Write-Host "Build complete. Run: dist\XVALite\XVALite.exe  (ship the whole dist\XVALite folder)"
}
