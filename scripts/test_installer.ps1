<# Isolated installer acceptance. Uses a test-only AppId and creates no shortcuts. #>
param(
    [Parameter(Mandatory=$true)][string]$SourceDirectory,
    [string]$PreviousSourceDirectory = '',
    [string]$OutputDirectory = 'artifacts\installer-acceptance',
    [string]$Compiler = ''
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $Compiler) { $Compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path -LiteralPath $Compiler)) { throw 'Inno Setup 6 is required for installer acceptance.' }
function In-Repo([string]$path) {
    $absolute = [IO.Path]::GetFullPath((Join-Path $repo $path))
    if (-not $absolute.StartsWith($repo + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Acceptance paths must remain inside the checkout.'
    }
    return $absolute
}
$payload = In-Repo $SourceDirectory
$output = In-Repo $OutputDirectory
$run = Join-Path $output ([guid]::NewGuid().ToString('N'))
$target = Join-Path $run 'installed'
$profile = Join-Path $run 'profile'
New-Item -ItemType Directory -Force -Path $run, $profile | Out-Null
function Run-Checked([string]$file, [string[]]$arguments, [int]$timeout = 180000) {
    $process = Start-Process -FilePath $file -ArgumentList $arguments -PassThru -WindowStyle Hidden
    if (-not $process.WaitForExit($timeout)) { $process.Kill(); throw "Timed out: $file" }
    if ($process.ExitCode -ne 0) { throw "$file exited $($process.ExitCode). See $run" }
}
function Compile-Test([string]$source, [string]$name, [string]$version = '') {
    $destination = Join-Path $run $name
    New-Item -ItemType Directory -Force -Path $destination | Out-Null
    $arguments = @('/DAcceptanceBuild', "/DSourceDir=$source", "/DBuildOutputDir=$destination")
    if ($version) { $arguments += "/DAppVersion=$version" }
    & $Compiler @arguments (Join-Path $repo 'installer.iss') *> (Join-Path $run "$name-compile.log")
    if ($LASTEXITCODE -ne 0) { throw "Acceptance installer compilation failed: $name" }
    return Join-Path $destination 'PVS-Acceptance-Setup.exe'
}
function Install-Test([string]$setup, [string]$name) {
    Run-Checked $setup @('/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS', '/TASKS=""',
        ('/DIR="' + $target + '"'), ('/LOG="' + (Join-Path $run "$name-install.log") + '"'))
}
function Check-Profile {
    foreach ($item in $script:sentinels.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $item.Key) -or
                (Get-FileHash -LiteralPath $item.Key -Algorithm SHA256).Hash -ne $item.Value) {
            throw "Installer modified retained user-data fixture: $($item.Key)"
        }
    }
}
function Check-Installed([string]$name) {
    $exe = Join-Path $target 'PlaguesVoiceStudio030Experimental.exe'
    foreach ($mode in @('--self-test', '--ui-self-test')) {
        $report = Join-Path $run ($name + '-' + $mode.TrimStart('-') + '.json')
        Run-Checked $exe @($mode, ('"' + $report + '"'))
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if ($result.status -ne 'passed') { throw "Installed $name $mode failed." }
    }
    Check-Profile
}
function Seed-UserPlugin {
    $path = Join-Path $target 'plugins\retained-user-plugin\notes.txt'
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
    [IO.File]::WriteAllText($path, 'User-owned plugin files must survive reinstall and uninstall.')
    $script:sentinels[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}
$sentinels = @{}
foreach ($folder in @('PlaguesVoiceStudio-v030-Experimental', 'PlaguesVoiceStudio')) {
    foreach ($file in @('voices\retained-reference.wav', 'engines\registry.json', 'settings.json', 'models\retained-weight.marker')) {
        $path = Join-Path (Join-Path $profile $folder) $file
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
        [IO.File]::WriteAllText($path, "Acceptance fixture: $folder / $file")
        $sentinels[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    }
}
$oldQt = $env:QT_QPA_PLATFORM
$oldLocalData = $env:LOCALAPPDATA
$env:QT_QPA_PLATFORM = 'offscreen'; $env:LOCALAPPDATA = $profile
$steps = @()
$uninstalled = $false
try {
    if ($PreviousSourceDirectory) {
        $previous = Compile-Test (In-Repo $PreviousSourceDirectory) 'previous' '0.3.0'
        Install-Test $previous 'previous'
        Check-Installed 'previous'
        Seed-UserPlugin
        $steps += 'previous-0.3-payload-install'
    }
    $setup = Compile-Test $payload 'candidate'
    Install-Test $setup 'candidate'
    Check-Installed 'candidate'
    if (-not $PreviousSourceDirectory) { Seed-UserPlugin }
    $steps += $(if ($PreviousSourceDirectory) { 'upgrade-from-previous-payload' } else { 'clean-install' })
    Install-Test $setup 'reinstall'
    Check-Installed 'reinstall'
    $steps += 'reinstall-and-second-launch'
    Run-Checked (Join-Path $target 'unins000.exe') @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    $uninstalled = $true
    Check-Profile
    if (Test-Path -LiteralPath (Join-Path $target 'PlaguesVoiceStudio030Experimental.exe')) { throw 'Uninstall left the application executable.' }
    $steps += 'uninstall-preserves-data'
    @{status='passed'; steps=$steps; profile=$profile; application=$target; fixture_files=$sentinels.Count} |
        ConvertTo-Json -Depth 5 | Set-Content (Join-Path $run 'result.json')
    Write-Host "Installer acceptance passed: $run"
} finally {
    if (-not $uninstalled -and (Test-Path -LiteralPath (Join-Path $target 'unins000.exe'))) {
        Run-Checked (Join-Path $target 'unins000.exe') @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    }
    $env:QT_QPA_PLATFORM = $oldQt; $env:LOCALAPPDATA = $oldLocalData
}
