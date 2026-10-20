<# Explicit local acceptance using already installed weights and reference audio. #>
param([string]$ApplicationDirectory = 'dist\ReleaseCandidate\PlaguesVoiceStudio030Experimental',
      [string]$ReportDirectory = 'artifacts\release-ready-rc1\frozen-speech',
      [ValidateSet('nano','turbo','english','multilingual','qwen06','qwen17','index25','kokoro')]
      [string[]]$Cases = @('nano','multilingual','qwen06','qwen17','index25','kokoro'))
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$exe = Join-Path ([IO.Path]::GetFullPath((Join-Path $repo $ApplicationDirectory))) 'PlaguesVoiceStudio030Experimental.exe'
$output = [IO.Path]::GetFullPath((Join-Path $repo $ReportDirectory))
if (-not $output.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Acceptance outputs must stay inside this checkout.' }
New-Item -ItemType Directory -Force -Path $output | Out-Null
$reference = Join-Path $repo 'artifacts\gpu-model-audit\reference.wav'
if (-not (Test-Path -LiteralPath $reference)) { throw 'Prepare the local reference fixture before this explicit inference test.' }
$models = @{
    nano = @('chatterbox','nano','en'); turbo = @('chatterbox','turbo','en'); english = @('chatterbox','english','en')
    multilingual = @('chatterbox','multilingual-v3','en')
    qwen06 = @('qwen3','Qwen/Qwen3-TTS-12Hz-0.6B-Base','English')
    qwen17 = @('qwen3','Qwen/Qwen3-TTS-12Hz-1.7B-Base','English')
    index25 = @('index25','IndexTeam/IndexTTS-2.5','EN')
}
$old = @{}
foreach ($key in @('HF_HUB_OFFLINE','TRANSFORMERS_OFFLINE','OMP_NUM_THREADS','MKL_NUM_THREADS')) { $old[$key] = [Environment]::GetEnvironmentVariable($key) }
$env:HF_HUB_OFFLINE='1'; $env:TRANSFORMERS_OFFLINE='1'; $env:OMP_NUM_THREADS='6'; $env:MKL_NUM_THREADS='6'
try {
    foreach ($case in $Cases) {
        $report = Join-Path $output "$case-result.json"
        if ($case -eq 'kokoro') { $arguments = @('--kokoro-self-test', ('"'+$report+'"')) }
        else {
            $model = $models[$case]
            $request = Join-Path $output "$case-request.json"
            @{engine=$model[0]; model=$model[1]; language=$model[2]; device='cpu'; voice_path=$reference;
              text="Good evening. You're listening to Goodneighbor Blues."; max_chars=180; pause_ms=100} |
                ConvertTo-Json | Set-Content -LiteralPath $request -Encoding utf8
            $arguments = @('--speech-self-test', ('"'+$request+'"'), ('"'+$report+'"'))
        }
        $process = Start-Process -FilePath $exe -ArgumentList $arguments -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit(660000)) { $process.Kill(); throw "Frozen speech check timed out: $case" }
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw "Frozen speech check failed: $case; inspect $output" }
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if ($result.status -ne 'passed') { throw "Frozen speech check failed: $case; inspect $report" }
        Write-Output "$case passed"
    }
} finally {
    foreach ($key in $old.Keys) { [Environment]::SetEnvironmentVariable($key, $old[$key]) }
}
