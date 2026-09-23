param([string]$Port = "")
$ErrorActionPreference = "Stop"
$venv = Join-Path $env:LOCALAPPDATA "DarbakTPMS\venv"
$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv $venv }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv $venv }
    else { throw "Install Python 3, then run this same command." }
    if ($LASTEXITCODE -ne 0) { throw "Python environment creation failed." }
}
& $python -m pip install --quiet --disable-pip-version-check "pyserial==3.5" "esptool==4.8.1"
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
$desktop = [Environment]::GetFolderPath("Desktop")
$sessionArgs = @((Join-Path $PSScriptRoot "obd_tpms_capture.py"), "--output", $desktop)
if ($Port) { $sessionArgs += @("--port", $Port) }
& $python @sessionArgs
if ($LASTEXITCODE -ne 0) { throw "Test stopped. Send the TPMS_OBD ZIP shown above, if created." }
