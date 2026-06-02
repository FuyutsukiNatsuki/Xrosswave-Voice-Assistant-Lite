# Build a standalone Windows executable with PyInstaller.
#
# Usage (from the repo root):
#   .\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
#   powershell -ExecutionPolicy Bypass -File scripts\build_exe.ps1
#
# Output: dist\XVALite\XVALite.exe (one-dir build; ship the whole XVALite folder).
# For a single-file exe, add --onefile (slower startup, larger). Drop --windowed
# to keep a console window for debugging.

$ErrorActionPreference = "Stop"
$py = "C:\XVALite\.venv\Scripts\python.exe"

& $py -m PyInstaller --noconfirm --clean --windowed --name XVALite `
    --paths src `
    --collect-all soundfile `
    --collect-all sounddevice `
    --collect-all parselmouth `
    xvalite_app.py

Write-Host ""
Write-Host "Build complete. Run: dist\XVALite\XVALite.exe"
