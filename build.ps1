$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw '请先运行 uv venv --python 3.13 .venv，并安装 requirements.txt。'
}
# Avoid DLLs from unrelated tools on PATH (e.g. Poppler's ICU, which is incompatible with Qt).
$originalPath = $env:PATH
$taskPythonBase = (& $pythonExe -c 'import sys; print(sys.base_prefix)').Trim()
try {
    $env:PATH = "$PSScriptRoot\.venv\Scripts;$taskPythonBase;$env:WINDIR\System32;$env:WINDIR"
    & $pythonExe -m PyInstaller --clean --noconfirm --windowed --onedir --name '汽水音乐助手' --icon 'qishui/assets/app.ico' --add-data 'qishui/assets;qishui/assets' --collect-all rapidocr_onnxruntime --collect-binaries onnxruntime main.py
    $buildExit = $LASTEXITCODE
} finally {
    $env:PATH = $originalPath
}
if ($buildExit -ne 0) { throw '打包失败' }
$executable = Join-Path $PSScriptRoot 'dist\汽水音乐助手\汽水音乐助手.exe'
$wsh = New-Object -ComObject WScript.Shell
$shortcut = $wsh.CreateShortcut((Join-Path $PSScriptRoot '启动汽水音乐助手.lnk'))
$shortcut.TargetPath = $executable
$shortcut.WorkingDirectory = Split-Path -Parent $executable
$shortcut.Description = '汽水音乐助手 · 本地运行'
$shortcut.Save()
Write-Output $executable
