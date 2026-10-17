<#
Optional IndexTTS-2.5 setup. Requires git, uv, network and license review.
New engine runtimes use the permanent PlaguesVoiceStudio AppData path.
This does not modify stable/Chatterbox environments or redistribute the weights.
#>
param(
    [string]$RepositoryDir = "",
    [switch]$DownloadModels,
    [switch]$LicenseReviewed
)
$ErrorActionPreference = 'Stop'
if (-not $RepositoryDir) {
    $old = Join-Path $env:LOCALAPPDATA 'PlaguesVoiceStudio-v030-Experimental\engines\index-tts'
    $new = Join-Path $env:LOCALAPPDATA 'PlaguesVoiceStudio\engines\index-tts'
    $RepositoryDir = if (Test-Path (Join-Path $old 'indextts\infer_v2_5.py')) { $old } else { $new }
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
}
Push-Location $RepositoryDir
try {
    # Avoid '--all-extras': it can pull optional DeepSpeed dependencies problematic on Windows.
    & uv sync
    if ($LASTEXITCODE -ne 0) { throw 'IndexTTS uv environment setup failed.' }
    $python = Join-Path $RepositoryDir '.venv\Scripts\python.exe'
    if (-not (Test-Path $python)) { throw 'IndexTTS Python not created.' }
    if ($DownloadModels) {
        & $python -c 'from huggingface_hub import snapshot_download; snapshot_download(repo_id="IndexTeam/IndexTTS-2.5", local_dir="checkpoints")'
        if ($LASTEXITCODE -ne 0) { throw 'Model checkpoint download failed.' }
    } else {
        Write-Host 'Model download skipped. Run again with -DownloadModels to retrieve IndexTeam/IndexTTS-2.5 checkpoints.'
    }
    Write-Host 'Set IndexTTS Python to:' $python
    Write-Host 'Set IndexTTS repository to:' $RepositoryDir
    Write-Host 'In Engine Lab, use Test selected engine before attempting generation.'
} finally { Pop-Location }
