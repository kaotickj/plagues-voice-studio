param([string]$PythonExecutable = '')
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $PythonExecutable) {
    $candidates = @((Join-Path $repo '.venv\Scripts\python.exe'),
                    (Join-Path $repo 'plugins\dj-writer\.venv-build\Scripts\python.exe'))
    $PythonExecutable = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $PythonExecutable) { $PythonExecutable = 'python' }
}
Push-Location $repo
try { & $PythonExecutable launcher.py }
finally { Pop-Location }
