$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $PSCommandPath
$wrapper = Join-Path $scriptDir 'invoke_imagegen.py'

if (-not (Test-Path -LiteralPath $wrapper)) {
    throw "No cross-platform imagegen wrapper found next to this PowerShell shim."
}

if ($env:IMAGEGEN_PYTHON) {
    $pythonExe = $env:IMAGEGEN_PYTHON
}
else {
    $python = Get-Command python -ErrorAction SilentlyContinue
    if ($python) {
        $pythonExe = $python.Source
    }
    else {
        $python3 = Get-Command python3 -ErrorAction SilentlyContinue
        if ($python3) {
            $pythonExe = $python3.Source
        }
        else {
            throw "Python was not found. Install Python 3.10+ or set IMAGEGEN_PYTHON to a Python executable."
        }
    }
}

& $pythonExe $wrapper @args
exit $LASTEXITCODE
