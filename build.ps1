param([string]$PythonExe = (Join-Path $PSScriptRoot '.venv\Scripts\python.exe'))
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath $PythonExe)) { throw 'Install requirements-dev.txt in a virtual environment first.' }
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
$originalPath = $env:PATH
$taskPythonBase = (& $PythonExe -c 'import sys; print(sys.base_prefix)').Trim()
try {
    $env:PATH = "$(Split-Path -Parent $PythonExe);$taskPythonBase;$env:WINDIR\System32;$env:WINDIR"
    & $PythonExe -m PyInstaller --clean --noconfirm --windowed --onedir --name 'USBInterfaceLab' --exclude-module rapidocr_onnxruntime --exclude-module onnxruntime --exclude-module cv2 --exclude-module numpy --exclude-module PIL main.py
    $taskBuildExit = $LASTEXITCODE
} finally {
    $env:PATH = $originalPath
}
if ($taskBuildExit -ne 0) { throw 'Demo build failed.' }
Write-Output (Join-Path $PSScriptRoot 'dist\USBInterfaceLab\USBInterfaceLab.exe')
