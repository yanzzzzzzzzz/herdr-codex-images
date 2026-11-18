param([Parameter(Mandatory=$true)][string]$Root,[string]$Command='open',[string[]]$Rest)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'windows-common.ps1')
$state = Get-HciState $Root
if (-not $state) { throw 'No active installation.' }
$runtime = Assert-HciChild $Root (Join-Path $Root ('versions\' + $state.version))
switch ($Command) {
    'open' {
        $env:HERDR_APP_HOME = Join-Path $Root 'app-home'
        $core = Join-Path $env:LOCALAPPDATA 'Programs\herdr-core'
        $env:Path = (Join-Path $runtime 'codex\bin') + ';' + $core + ';' + $env:Path + ';' + (Join-Path $runtime 'core')
        Start-Process -FilePath (Join-Path $runtime 'herdr\herdr-app.exe') -WorkingDirectory $env:USERPROFILE -WindowStyle Normal | Out-Null
    }
    'doctor' {
        Test-HciRuntime $runtime
        & (Join-Path $runtime 'codex\bin\codex.exe') --help | Out-Null
        if ($LASTEXITCODE) { throw 'Codex help check failed.' }
        & (Join-Path $runtime 'codex\codex-path\rg.exe') --version | Out-Null
        if ($LASTEXITCODE) { throw 'Search companion failed.' }
        Write-Host "OK: $($state.version), isolated app, Codex, core and file hashes."
    }
    { $_ -in @('status','ls','shot') } {
        $env:HERDR_APP_HOME = Join-Path $Root 'app-home'
        & (Join-Path $runtime 'herdr\herdr-app.exe') $Command @Rest | Out-Host
        if ($LASTEXITCODE) { throw 'Herdr command failed.' }
    }
    'update' {
        $script = Assert-HciChild $Root (Join-Path $Root ('.update-' + [guid]::NewGuid().ToString('N') + '.ps1'))
        try {
            Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/yanzzzzzzzzz/herdr-codex-images/main/install.ps1' -OutFile $script
            & (Get-HciPowerShell) -NoProfile -ExecutionPolicy Bypass -File $script -InstallRoot $Root
            if ($LASTEXITCODE) { throw 'Update failed.' }
        } finally { if (Test-Path -LiteralPath $script) { Remove-Item -LiteralPath $script } }
    }
    'rollback' {
        if (-not $state.previous -or $state.previous -notmatch '^v[0-9][A-Za-z0-9.-]*$') { throw 'No previous release to restore.' }
        $previous = Assert-HciChild $Root (Join-Path $Root ('versions\' + $state.previous))
        Test-HciRuntime $previous
        $lock = [IO.File]::Open((Join-Path $Root '.install.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        try {
            $current = $state.version; $state.version = $state.previous; $state.previous = $current
            Set-HciState $Root $state
        } finally { $lock.Dispose() }
        Write-Host 'Restored previous release. Reopen Herdr Images when convenient; running terminals are unchanged.'
    }
    'uninstall' {
        $lock = [IO.File]::Open((Join-Path $Root '.install.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
        try {
            foreach ($profile in $state.profiles) {
                $document = Get-HciProfileDocument $profile
                Save-HciProfile $Root $document (Remove-HciProfileBlock $document.Text)
            }
            if ($state.shortcut -and (Test-Path -LiteralPath $state.shortcut)) {
                Initialize-HciShortcut
                $link = [HciWindowsShortcutV1]::Load($state.shortcut)
                if ($link[0] -eq $script:HciOwner -and $link[1].Contains($Root + '\bootstrap.ps1')) { Remove-Item -LiteralPath $state.shortcut }
            }
            foreach ($name in @('bootstrap.ps1','herdr-images.cmd','install.json')) {
                $path = Assert-HciChild $Root (Join-Path $Root $name)
                if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
            }
        } finally { $lock.Dispose() }
        Write-Host 'Removed managed entry/shortcut/profile blocks. Settings, backups and versions retained. No running app, terminal or core was stopped.'
    }
    default { throw 'Commands: open, doctor, status, ls, shot, update, rollback, uninstall' }
}
