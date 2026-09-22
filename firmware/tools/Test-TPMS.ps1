param(
    [string]$Port = "",
    [switch]$SkipFlash,
    [switch]$Guided,
    [switch]$LiveCalibration,
    [switch]$ResumeCalibration,
    [ValidateRange(1, 3600)]
    [int]$Seconds = 180
)
$ErrorActionPreference = "Stop"
if ($ResumeCalibration) { $LiveCalibration = $true }
if ($Guided -and $LiveCalibration) { throw "Choose LiveCalibration or Guided, not both." }
$venv = Join-Path $env:LOCALAPPDATA "DarbakTPMS\venv"
$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $python)) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3 -m venv $venv
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        & python -m venv $venv
    } else {
        throw "Python 3 is required. Install it, then run this same command."
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not create the Python environment." }
}
& $python -m pip install --quiet --disable-pip-version-check "pyserial==3.5" "esptool==4.8.1"
if ($LASTEXITCODE -ne 0) { throw "Could not install the serial/flashing dependencies." }
$captureArgs = @((Join-Path $PSScriptRoot "tpms_capture.py"), "--seconds", "$Seconds", "--label", "passive_mixed_sensors")
if ($LiveCalibration) { $captureArgs += "--live-calibration" }
if ($ResumeCalibration) {
    $baseline = Join-Path $PSScriptRoot "calibration-baseline.jsonl"
    if (-not (Test-Path -LiteralPath $baseline)) { throw "This kit does not include previous calibration evidence." }
    $captureArgs += @("--baseline", $baseline)
}
if ($Guided) { $captureArgs += "--guided" }
if (-not $SkipFlash) { $captureArgs += "--flash" }
if ($Port) { $captureArgs += @("--port", $Port) }
& $python @captureArgs
if ($LASTEXITCODE -ne 0) { throw "The TPMS session reported an error. See the saved ZIP if one was created." }
