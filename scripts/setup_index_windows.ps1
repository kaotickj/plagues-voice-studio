<#
Optional IndexTTS-2.5 setup. Requires git, uv, network and license review.
New engine runtimes and models use the shared PlaguedAI library.
This does not modify stable/Chatterbox environments or redistribute the weights.
#>
param(
    [string]$RepositoryDir = "",
    [switch]$DownloadModels,
    [switch]$LicenseReviewed,
    [string]$ModelDirectory = "",
    [ValidateSet('CPU', 'CUDA')][string]$Backend = 'CPU'
)
$ErrorActionPreference = 'Stop'
$studioRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$sharedRoot = if ($env:PLAGUED_AI_HOME) { $env:PLAGUED_AI_HOME } else { Join-Path $env:LOCALAPPDATA 'PlaguedAI' }
if (-not $ModelDirectory) { $ModelDirectory = Join-Path $sharedRoot 'models\index-tts\2.5' }
if (-not $RepositoryDir) {
    $old = Join-Path $env:LOCALAPPDATA 'PlaguesVoiceStudio-v030-Experimental\engines\index-tts'
    $previous = Join-Path $env:LOCALAPPDATA 'PlaguesVoiceStudio\engines\index-tts'
    $new = Join-Path $sharedRoot 'runtimes\index-tts-2.5'
    $RepositoryDir = if (Test-Path (Join-Path $old 'indextts\infer_v2_5.py')) { $old } elseif (Test-Path (Join-Path $previous 'indextts\infer_v2_5.py')) { $previous } else { $new }
}
if (-not $LicenseReviewed) {
    throw 'Read the upstream IndexTTS Bilibili Model Use License and DISCLAIMER first, then rerun with -LicenseReviewed.'
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'Git is required.' }
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) { throw 'Install uv from https://docs.astral.sh/uv/ first.' }
if (-not (Test-Path (Join-Path $RepositoryDir 'indextts\infer_v2_5.py'))) {
    $parent = Split-Path $RepositoryDir -Parent
    New-Item -ItemType Directory -Force $parent | Out-Null
    & git clone https://github.com/index-tts/index-tts.git $RepositoryDir
    if ($LASTEXITCODE -ne 0) { throw 'Unable to clone IndexTTS repository.' }
    & git -C $RepositoryDir checkout d9e41aac89fd00b3d71497fddb287b7f24613712
    if ($LASTEXITCODE -ne 0) { throw 'Unable to select the tested IndexTTS source revision.' }
}
& py -3.11 (Join-Path $studioRoot 'scripts\patch_index_windows_compat.py') --repo $RepositoryDir
if ($LASTEXITCODE -ne 0) { throw 'IndexTTS compatibility requirements could not be applied.' }
Push-Location $RepositoryDir
try {
    # Avoid '--all-extras': it can pull optional DeepSpeed dependencies problematic on Windows.
    $torchIndex = if ($Backend -eq 'CPU') { 'https://download.pytorch.org/whl/cpu' } else { 'https://download.pytorch.org/whl/cu128' }
    & uv sync --index "pytorch-cuda=$torchIndex"
    if ($LASTEXITCODE -ne 0) { throw 'IndexTTS uv environment setup failed.' }
    $python = Join-Path $RepositoryDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { throw 'IndexTTS Python not created.' }
    & uv pip check --python $python
    if ($LASTEXITCODE -ne 0) { throw 'IndexTTS dependency check failed.' }
    if ($DownloadModels) {
        $previousWeights = Join-Path $RepositoryDir 'checkpoints'
        if (-not (Test-Path -LiteralPath $ModelDirectory) -and (Test-Path -LiteralPath (Join-Path $previousWeights 'config.yaml'))) {
            # Keep an existing installation usable until explicit consolidation.
            $ModelDirectory = $previousWeights
        }
        & $python -c 'import sys; from huggingface_hub import snapshot_download; snapshot_download(repo_id="IndexTeam/IndexTTS-2.5", local_dir=sys.argv[1])' $ModelDirectory
        if ($LASTEXITCODE -ne 0) { throw 'Model checkpoint download failed.' }
    } else {
        Write-Host 'Model download skipped. Run again with -DownloadModels to retrieve IndexTeam/IndexTTS-2.5 checkpoints.'
    }
    Write-Host 'Set IndexTTS Python to:' $python
    Write-Host 'Set IndexTTS repository to:' $RepositoryDir
    Write-Host 'IndexTTS model directory:' $ModelDirectory
    Write-Host 'In Engine Lab, use Test selected engine before attempting generation.'
} finally { Pop-Location }
