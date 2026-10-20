param([string]$PythonExecutable = 'python', [switch]$SkipInstall,
      [string]$OutputDirectory = 'dist', [switch]$SkipInstaller,
      [string]$InnoSetupCompiler = '')
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        & $PythonExecutable -m venv .venv-build
        if ($LASTEXITCODE -ne 0) { throw 'Could not create build environment.' }
    }
    if (-not $SkipInstall) {
        & $python -m pip install -r requirements-build.txt
        if ($LASTEXITCODE -ne 0) { throw 'Build dependency installation failed.' }
    }
    & $python prepare_icon.py
    if ($LASTEXITCODE -ne 0) { throw 'Icon conversion failed.' }
    $previousQt = $env:QT_QPA_PLATFORM
    $previousHome = $env:GOODNEIGHBOR_DJ_HOME
    $previousPath = $env:PATH
    try {
        # Prevent unrelated developer-tool DLLs (Poppler/libheif, etc.) on PATH
        # from being collected instead of the Windows/Qt runtime dependencies.
        $env:PATH = @((Split-Path $python), (Join-Path $env:SystemRoot 'System32'), $env:SystemRoot) -join ';'
        $env:QT_QPA_PLATFORM = 'offscreen'
        $env:GOODNEIGHBOR_DJ_HOME = Join-Path $PSScriptRoot 'build\test-profile'
        & $python -m unittest discover -p 'tests*.py' -v
        if ($LASTEXITCODE -ne 0) { throw 'DJ Writer regression tests failed.' }
        & $python -m PyInstaller --noconfirm --clean --distpath $OutputDirectory 'Goodneighbor Plague Radio DJ Writer.spec'
        if ($LASTEXITCODE -ne 0) { throw 'Windows packaging failed.' }
        $appName = 'Goodneighbor Plague Radio DJ Writer'
        $packageFolder = Join-Path (Join-Path $PSScriptRoot $OutputDirectory) $appName
        $exe = Join-Path $packageFolder "$appName.exe"
        $report = Join-Path $PSScriptRoot ('build\smoke-' + [guid]::NewGuid().ToString('N') + '.json')
        $process = Start-Process -FilePath $exe -ArgumentList @('--smoke-test', ('"' + $report + '"')) -PassThru -WindowStyle Hidden
        if (-not $process.WaitForExit(60000)) {
            $process.Kill()
            throw 'Frozen application smoke test timed out.'
        }
        if ($process.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $report)) { throw 'Frozen application smoke test failed.' }
        $result = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json
        if (-not $result.ok -or -not $result.icon) { throw 'Frozen icon verification failed.' }
        New-Item -ItemType Directory -Force artifacts | Out-Null
        $version = (& $python -c "import ast; t=ast.parse(open('goodneighbor_dj.py',encoding='utf-8').read()); print(next(ast.literal_eval(n.value) for n in t.body if isinstance(n,ast.Assign) and any(isinstance(k,ast.Name) and k.id=='VERSION' for k in n.targets)))").Trim()
        if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Invalid DJ Writer version.' }
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot '..\..\LICENSE') -Destination (Join-Path $packageFolder 'LICENSE') -Force
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination (Join-Path $packageFolder 'README.md') -Force
        $zip = Join-Path $PSScriptRoot "artifacts\DJ-Writer-$version-Windows-Portable.zip"
        Compress-Archive -LiteralPath $packageFolder -DestinationPath $zip -Force
        & $python -c "import sys,zipfile; z=zipfile.ZipFile(sys.argv[1]); assert z.testzip() is None, 'Portable archive integrity check failed'" $zip
        if ($LASTEXITCODE -ne 0) { throw 'Portable archive integrity check failed.' }
        $packages = @($zip)
        if (-not $SkipInstaller) {
            if (-not $InnoSetupCompiler) {
                $InnoSetupCompiler = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6\ISCC.exe'
            }
            if (-not (Test-Path -LiteralPath $InnoSetupCompiler)) { throw 'Inno Setup 6 is required. Install it or pass -SkipInstaller for a portable-only build.' }
            $installerOutput = Join-Path $PSScriptRoot 'artifacts'
            & $InnoSetupCompiler "/DAppVersion=$version" "/DSourceDir=$packageFolder" "/DBuildOutputDir=$installerOutput" (Join-Path $PSScriptRoot 'installer.iss')
            if ($LASTEXITCODE -ne 0) { throw 'DJ Writer installer compilation failed.' }
            $installer = Join-Path $installerOutput "DJ-Writer-Setup-$version.exe"
            if (-not (Test-Path -LiteralPath $installer)) { throw 'Installer compiler produced no setup executable.' }
            $packages += $installer
        }
        $checksums = foreach ($package in $packages) {
            $hash = (Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash.ToLowerInvariant()
            "$hash  $([IO.Path]::GetFileName($package))"
        }
        $checksums | Set-Content artifacts\SHA256SUMS.txt -Encoding utf8
        Write-Host "Ready for testing: $exe"
        Write-Host "Portable archive: $zip"
    } finally {
        $env:QT_QPA_PLATFORM = $previousQt
        $env:GOODNEIGHBOR_DJ_HOME = $previousHome
        $env:PATH = $previousPath
    }
} finally { Pop-Location }
