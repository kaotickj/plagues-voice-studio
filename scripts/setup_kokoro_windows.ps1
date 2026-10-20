<# Install Kokoro in its own shared Python environment; reuse existing model files. #>
param([string]$EnvironmentDir = '', [string]$ModelDirectory = '',
      [string]$PythonVersion = '3.12', [ValidateSet('CPU', 'DirectML')][string]$Backend = 'DirectML',
      [switch]$DownloadModels)
$ErrorActionPreference = 'Stop'
$sharedRoot = if ($env:PLAGUED_AI_HOME) { $env:PLAGUED_AI_HOME } else { Join-Path $env:LOCALAPPDATA 'PlaguedAI' }
if (-not $EnvironmentDir) {
    $EnvironmentDir = Join-Path $sharedRoot $(if ($Backend -eq 'DirectML') { 'runtimes\python\kokoro-directml' } else { 'runtimes\python\kokoro-onnx' })
}
if (-not $ModelDirectory) { $ModelDirectory = Join-Path $sharedRoot 'models\speech\kokoro' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$python = Join-Path $EnvironmentDir 'Scripts\python.exe'
if (-not (Test-Path -LiteralPath $python)) {
    & py "-$PythonVersion" -m venv $EnvironmentDir
    if ($LASTEXITCODE -ne 0) { throw "Python $PythonVersion is required." }
}
& $python -c 'import importlib.metadata as m,sys; packages={d.metadata["Name"].lower().replace("_","-") for d in m.distributions()}; expected=sys.argv[1]; conflicts=packages.intersection({"onnxruntime","onnxruntime-gpu","onnxruntime-directml"})-{expected}; sys.exit("Choose a separate Kokoro environment; conflicting runtimes: "+", ".join(sorted(conflicts)) if conflicts else 0)' $(if ($Backend -eq 'DirectML') { 'onnxruntime-directml' } else { 'onnxruntime' })
if ($LASTEXITCODE -ne 0) { throw 'Refusing to mix ONNX Runtime variants in one environment.' }
$onnxPackage = if ($Backend -eq 'DirectML') { 'onnxruntime-directml==1.24.4' } else { 'onnxruntime==1.31.0' }
& $python -m pip install $onnxPackage 'soundfile==0.14.0' 'numpy==2.5.4' 'espeakng-loader==0.2.4' 'phonemizer==3.4.0'
if ($LASTEXITCODE -ne 0) { throw 'Kokoro installation failed.' }
if ($Backend -eq 'DirectML') {
    & $python -m pip install 'onnx==1.23.2'
    if ($LASTEXITCODE -ne 0) { throw 'ONNX compatibility tool installation failed.' }
}
# DirectML supplies the same Python API as onnxruntime. Avoid installing the
# conflicting CPU distribution pulled by kokoro-onnx's upstream dependency list.
& $python -m pip install --no-deps 'kokoro-onnx==0.6.1'
if ($LASTEXITCODE -ne 0) { throw 'Kokoro package installation failed.' }
if ($DownloadModels) {
    New-Item -ItemType Directory -Force -Path $ModelDirectory | Out-Null
    $files = @(
        @('kokoro-v1.0.int8.onnx', 'ae315a79b623f244700e4afb9246c46a26066782e049ba174bf3ba433970ee9c'),
        @('voices-v1.0.bin', 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d')
    )
    foreach ($file in $files) {
        $destination = Join-Path $ModelDirectory $file[0]
        if (Test-Path -LiteralPath $destination) {
            if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file[1]) {
                throw "Existing file differs from the pinned model: $destination. Select a separate folder; nothing was overwritten."
            }
            continue
        }
        $partial = $destination + '.' + [guid]::NewGuid().ToString('N') + '.partial'
        try {
            Invoke-WebRequest -Uri ('https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/' + $file[0]) -OutFile $partial
            if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant() -ne $file[1]) { throw 'Model checksum mismatch.' }
            Move-Item -LiteralPath $partial -Destination $destination
        } finally {
            if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial }
        }
    }
}
& $python -I -u (Join-Path $repo 'optional_engine_runner.py') --probe kokoro $ModelDirectory
if ($LASTEXITCODE -ne 0) { throw 'Kokoro probe failed. Check the model directory or rerun with -DownloadModels.' }
Write-Host 'Kokoro Python:' $python
Write-Host 'Kokoro models:' $ModelDirectory
Write-Host 'Select Kokoro in Voice Engines. Default paths are detected automatically.'
