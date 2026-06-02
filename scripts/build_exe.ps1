# Build a standalone Windows executable with PyInstaller.
#
# Usage (from the repo root):
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
$py = "C:\XVALite\.venv\Scripts\python.exe"

# Make sure the icon exists.
if (-not (Test-Path "C:\XVALite\assets\icon.ico")) {
    & $py "C:\XVALite\scripts\make_icon.py"
}

$args = @(
    "--noconfirm", "--clean", "--windowed", "--name", "XVALite",
    "--paths", "src",
    "--icon", "assets\icon.ico",
    "--add-data", "assets\icon.ico;assets",
    "--collect-all", "soundfile",
    "--collect-all", "sounddevice",
    "--collect-all", "parselmouth"
)
if ($OneFile) { $args += "--onefile" }
$args += "xvalite_app.py"

& $py -m PyInstaller @args

Write-Host ""
if ($OneFile) {
    Write-Host "Build complete. Run: dist\XVALite.exe"
} else {
    Write-Host "Build complete. Run: dist\XVALite\XVALite.exe  (ship the whole dist\XVALite folder)"
}
