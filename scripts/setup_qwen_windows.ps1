<#
Optional, explicit setup for Qwen3-TTS. DOES NOT TOUCH the Chatterbox venv.
Requires 64-bit Python 3.12, network and several GB free storage.
Run only after reviewing https://github.com/QwenLM/Qwen3-TTS
#>
param(
    [string]$EnvironmentDir = "",
    [string]$PythonVersion = '3.12'
)
$ErrorActionPreference = 'Stop'
$sharedRoot = if ($env:PLAGUED_AI_HOME) { $env:PLAGUED_AI_HOME } else { Join-Path $env:LOCALAPPDATA 'PlaguedAI' }
if (-not $EnvironmentDir) {
    $old = Join-Path $env:LOCALAPPDATA 'PlaguesVoiceStudio-v030-Experimental\engines\qwen3'
    $previous = Join-Path $env:LOCALAPPDATA 'PlaguesVoiceStudio\engines\qwen3'
    $new = Join-Path $sharedRoot 'runtimes\python\qwen3-tts'
    $EnvironmentDir = if (Test-Path (Join-Path $old 'Scripts\python.exe')) { $old } elseif (Test-Path (Join-Path $previous 'Scripts\python.exe')) { $previous } else { $new }
}
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
Write-Host 'Installing OPTIONAL Qwen3-TTS in a separate environment.'
Write-Host 'Your Chatterbox environment, stable app, and saved voices will not be changed.'
if (-not (Test-Path "$EnvironmentDir\Scripts\python.exe")) {
    & py "-$PythonVersion" -m venv $EnvironmentDir
    if ($LASTEXITCODE -ne 0) { throw "Python $PythonVersion is required. Install it separately, then rerun." }
}
$python = Join-Path $EnvironmentDir 'Scripts\python.exe'
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip bootstrap failed.' }
& $python -m pip install qwen-tts==0.1.1 transformers==4.57.3 soundfile==0.14.0 safetensors==0.8.0
if ($LASTEXITCODE -ne 0) { throw 'Qwen3-TTS installation failed.' }
& $python (Join-Path $root 'optional_engine_runner.py') --probe qwen3
if ($LASTEXITCODE -ne 0) { throw 'Engine import test failed.' }
Write-Host 'In Optional Engine Lab, set Qwen3 Python to:'
Write-Host $python
Write-Host 'Model weights will download separately on first generation if not already cached.'
