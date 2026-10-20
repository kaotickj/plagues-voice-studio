<# Isolated DJ installer acceptance; no real app registration, profiles or shortcuts. #>
param([string]$SourceDirectory = 'dist\Goodneighbor Plague Radio DJ Writer',
      [string]$PreviousSourceDirectory = '', [string]$PreviousAppVersion = '0.9.2', [string]$Compiler = '')
$ErrorActionPreference = 'Stop'
$plugin = $PSScriptRoot
$repo = [IO.Path]::GetFullPath((Join-Path $plugin '..\..'))
if (-not $Compiler) { $Compiler = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
function In-Plugin([string]$path) {
    $absolute = [IO.Path]::GetFullPath((Join-Path $plugin $path))
    if (-not $absolute.StartsWith($plugin + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Payload must remain inside the DJ Writer checkout.' }
    return $absolute
}
$run = Join-Path $repo ('artifacts\dj-installer-acceptance\' + [guid]::NewGuid().ToString('N'))
$target = Join-Path $run 'installed'
$profile = Join-Path $run 'profile'
New-Item -ItemType Directory -Force -Path $run, $profile | Out-Null
$sentinels = @{}
foreach ($name in @('settings.json', 'libraries\advertiser.json', 'characters\dj.json', 'lore\reference.json', 'models\retained-weight.marker')) {
    $path = Join-Path $profile $name
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $path) | Out-Null
    [IO.File]::WriteAllText($path, 'Synthetic retained data: ' + $name)
    $sentinels[$path] = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
}
function Run-Checked([string]$file, [string[]]$arguments) {
    $p = Start-Process -FilePath $file -ArgumentList $arguments -PassThru -WindowStyle Hidden
    if (-not $p.WaitForExit(180000)) { $p.Kill(); throw "Timed out: $file" }
    if ($p.ExitCode -ne 0) { throw "$file exited $($p.ExitCode); inspect $run" }
}
function Check-Data {
    foreach ($item in $script:sentinels.GetEnumerator()) {
        if (-not (Test-Path -LiteralPath $item.Key) -or (Get-FileHash -LiteralPath $item.Key -Algorithm SHA256).Hash -ne $item.Value) { throw 'Installer changed retained user data.' }
    }
}
function Compile-Test([string]$source, [string]$name, [string]$version) {
    $out = Join-Path $run $name
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $arguments = @('/DAcceptanceBuild', "/DSourceDir=$source", "/DBuildOutputDir=$out")
    if ($version) { $arguments += "/DAppVersion=$version" }
    & $Compiler @arguments (Join-Path $plugin 'installer.iss') *> (Join-Path $run "$name-compile.log")
    if ($LASTEXITCODE -ne 0) { throw "Installer compilation failed: $name" }
    return Join-Path $out 'DJ-Writer-Acceptance-Setup.exe'
}
function Install-Test([string]$setup, [string]$name, [string]$expectedVersion = '') {
    Run-Checked $setup @('/SP-', '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', '/NOICONS',
        ('/DIR="' + $target + '"'), ('/LOG="' + (Join-Path $run "$name-install.log") + '"'))
    $report = Join-Path $run "$name-smoke.json"
    Run-Checked (Join-Path $target 'Goodneighbor Plague Radio DJ Writer.exe') @('--smoke-test', ('"' + $report + '"'))
    $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
    if (-not $result.ok -or -not $result.icon) { throw 'Installed DJ startup/icon check failed.' }
    if ($expectedVersion -and $result.version -ne $expectedVersion) { throw 'Previous payload does not match the declared installer version.' }
    Check-Data
}
$oldQt = $env:QT_QPA_PLATFORM; $oldHome = $env:GOODNEIGHBOR_DJ_HOME; $oldShared = $env:PLAGUED_AI_HOME
$env:QT_QPA_PLATFORM = 'offscreen'; $env:GOODNEIGHBOR_DJ_HOME = $profile; $env:PLAGUED_AI_HOME = Join-Path $profile 'PlaguedAI'
$uninstalled = $false; $steps = @()
try {
    if ($PreviousSourceDirectory) {
        Install-Test (Compile-Test (In-Plugin $PreviousSourceDirectory) 'previous' $PreviousAppVersion) 'previous' $PreviousAppVersion
        $steps += 'previous-payload-install'
    }
    $setup = Compile-Test (In-Plugin $SourceDirectory) 'candidate' ''
    Install-Test $setup 'candidate'
    $steps += $(if ($PreviousSourceDirectory) { 'upgrade' } else { 'clean-install' })
    Install-Test $setup 'reinstall'
    $steps += 'reinstall-and-repeated-startup'
    Run-Checked (Join-Path $target 'unins000.exe') @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    $uninstalled = $true
    Check-Data
    if (Test-Path -LiteralPath (Join-Path $target 'Goodneighbor Plague Radio DJ Writer.exe')) { throw 'Uninstaller left the application executable.' }
    $steps += 'uninstall-preserves-libraries'
    @{status='passed'; steps=$steps; fixture_files=$sentinels.Count; profile=$profile; application=$target} |
        ConvertTo-Json -Depth 5 | Set-Content (Join-Path $run 'result.json')
    Write-Host "DJ installer acceptance passed: $run"
} finally {
    if (-not $uninstalled -and (Test-Path -LiteralPath (Join-Path $target 'unins000.exe'))) {
        Run-Checked (Join-Path $target 'unins000.exe') @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART')
    }
    $env:QT_QPA_PLATFORM = $oldQt; $env:GOODNEIGHBOR_DJ_HOME = $oldHome; $env:PLAGUED_AI_HOME = $oldShared
}
