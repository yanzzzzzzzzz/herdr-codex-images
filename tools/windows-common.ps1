$ErrorActionPreference = 'Stop'
$script:HciOwner = 'herdr-codex-images/windows/v1'
$script:HciShortcutAssembly = Join-Path $PSScriptRoot 'windows-shortcut.dll'

function Initialize-HciShortcut {
    if (-not ('HciWindowsShortcutV1' -as [type])) { $null = [Reflection.Assembly]::Load([IO.File]::ReadAllBytes($script:HciShortcutAssembly)) }
}

function Get-HciSha256([string]$Path) {
    $stream = [IO.File]::OpenRead([IO.Path]::GetFullPath($Path))
    $sha = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}

function Get-HciPowerShell {
    Join-Path ([Environment]::GetFolderPath('System')) 'WindowsPowerShell\v1.0\powershell.exe'
}

function Assert-HciChild([string]$Root, [string]$Path) {
    $rootFull = [IO.Path]::GetFullPath($Root).TrimEnd('\')
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($rootFull + '\', [StringComparison]::OrdinalIgnoreCase)) { throw "Path is outside the installation: $full" }
    $cursor = $full
    while ($cursor.Length -ge $rootFull.Length) {
        if ((Test-Path -LiteralPath $cursor) -and ((Get-Item -LiteralPath $cursor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw "Managed path must not be a link: $cursor" }
        if ($cursor -ieq $rootFull) { break }
        $cursor = [IO.Path]::GetDirectoryName($cursor)
    }
    return $full
}

function Get-HciState([string]$Root) {
    $path = Assert-HciChild $Root (Join-Path $Root 'install.json')
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $state = [IO.File]::ReadAllText($path) | ConvertFrom-Json
    if ($state.owner -ne $script:HciOwner -or $state.version -notmatch '^v[0-9][A-Za-z0-9.-]*$') { throw 'Unmanaged or malformed installation state.' }
    return $state
}

function Set-HciState([string]$Root, $State) {
    $path = Assert-HciChild $Root (Join-Path $Root 'install.json')
    $temp = Assert-HciChild $Root (Join-Path $Root ('.state-' + [guid]::NewGuid().ToString('N')))
    [IO.File]::WriteAllText($temp, ($State | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
    if (Test-Path -LiteralPath $path) {
        $backup = Assert-HciChild $Root (Join-Path $Root ('backups\state-' + [guid]::NewGuid().ToString('N') + '.json'))
        [IO.File]::Replace($temp, $path, $backup)
    } else { [IO.File]::Move($temp, $path) }
}

function Get-HciProfileDocument([string]$Path) {
    $pathFull = [IO.Path]::GetFullPath($Path)
    for ($depth = 0; $depth -lt 20; $depth++) {
        if (-not (Test-Path -LiteralPath $pathFull)) { break }
        $item = Get-Item -LiteralPath $pathFull -Force
        if (-not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { break }
        $target = @($item.Target)[0]
        if (-not $target) { throw 'Cannot resolve profile link.' }
        $pathFull = if ([IO.Path]::IsPathRooted($target)) { $target } else { [IO.Path]::GetFullPath((Join-Path $item.DirectoryName $target)) }
    }
    if ($depth -eq 20) { throw 'Profile symbolic-link loop.' }
    $encoding = [Text.UTF8Encoding]::new($true)
    $text = ''
    $bytes = [byte[]]@()
    $existed = Test-Path -LiteralPath $pathFull -PathType Leaf
    if ($existed) {
        $bytes = [IO.File]::ReadAllBytes($pathFull)
        $offset = 0
        if ($bytes.Length -ge 3 -and $bytes[0] -eq 239 -and $bytes[1] -eq 187 -and $bytes[2] -eq 191) { $offset = 3 }
        elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 255 -and $bytes[1] -eq 254) { $encoding = [Text.UnicodeEncoding]::new($false,$true); $offset = 2 }
        elseif ($bytes.Length -ge 2 -and $bytes[0] -eq 254 -and $bytes[1] -eq 255) { $encoding = [Text.UnicodeEncoding]::new($true,$true); $offset = 2 }
        else {
            $encoding = [Text.UTF8Encoding]::new($false,$true)
            try { $null = $encoding.GetString($bytes) } catch { $encoding = [Text.Encoding]::GetEncoding([Globalization.CultureInfo]::CurrentCulture.TextInfo.ANSICodePage) }
        }
        $text = $encoding.GetString($bytes, $offset, $bytes.Length - $offset)
    }
    [pscustomobject]@{ Path=$pathFull; Text=$text; Encoding=$encoding; Bytes=$bytes; Existed=$existed }
}

function Remove-HciProfileBlock([string]$Text) {
    $begin = '(?m)^# BEGIN herdr-codex-images-installer\r?$'
    $end = '(?m)^# END herdr-codex-images-installer\r?$'
    $starts = [regex]::Matches($Text,$begin).Count
    $ends = [regex]::Matches($Text,$end).Count
    if ($starts -ne $ends -or $starts -gt 1) { throw 'Malformed managed profile block; profile unchanged.' }
    [regex]::Replace($Text, '(?ms)^# BEGIN herdr-codex-images-installer\r?\n.*?^# END herdr-codex-images-installer(?:\r?\n|\z)', '')
}

function Save-HciProfile([string]$Root, $Document, [string]$Text) {
    $backup = Assert-HciChild $Root (Join-Path $Root ('backups\profile-' + [guid]::NewGuid().ToString('N') + '.bak'))
    if (Test-Path -LiteralPath $Document.Path) { [IO.File]::Copy($Document.Path,$backup) }
    $directory = [IO.Path]::GetDirectoryName($Document.Path)
    [IO.Directory]::CreateDirectory($directory) | Out-Null
    [IO.File]::WriteAllText($Document.Path, $Text, $Document.Encoding)
}

function Test-HciRuntime([string]$Directory) {
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $Directory 'FILES.sha256'))) {
        if ($line -notmatch '^([a-f0-9]{64})  (.+)$') { throw 'Malformed runtime checksum.' }
        $hash = $Matches[1]; $relative = $Matches[2]
        $path = Assert-HciChild $Directory (Join-Path $Directory $relative)
        if ((Get-HciSha256 $path) -ine $hash) { throw "Runtime mismatch: $relative" }
    }
    foreach ($entry in @(@('herdr\herdr-app.exe','herdr-app 0.1.16'), @('codex\bin\codex.exe','codex-cli 0.169.1'), @('core\hc.exe','hc 0.1.21'))) {
        $version = & (Join-Path $Directory $entry[0]) --version
        if ($LASTEXITCODE -ne 0 -or $version.Trim() -ne $entry[1]) { throw "Unexpected runtime: $($entry[0])" }
    }
}

function Install-HciWindows {
    param([string]$Root,[string]$Payload,[string]$Version,[string]$ArchiveHash,[string]$SourceConfig,[string[]]$ProfilePaths,[string]$ShortcutDirectory,[switch]$NoShortcut)
    $old = Get-HciState $Root
    foreach ($name in @('versions','backups','app-home','bootstrap.ps1','herdr-images.cmd')) { $null = Assert-HciChild $Root (Join-Path $Root $name) }
    foreach ($name in @('bootstrap.ps1','herdr-images.cmd')) {
        $path = Join-Path $Root $name
        if ((Test-Path -LiteralPath $path) -and -not ([IO.File]::ReadAllText($path).Contains('HerdrCodexImages managed entry v1'))) { throw "Unmanaged entry exists: $path" }
    }
    if (-not $ProfilePaths) {
        if ($old) { $ProfilePaths = @($old.profiles) }
        else {
            $documents = [Environment]::GetFolderPath('MyDocuments')
            $ProfilePaths = @((Join-Path $documents 'WindowsPowerShell\profile.ps1'),(Join-Path $documents 'PowerShell\profile.ps1'))
        }
    }
    $documentsToWrite = @()
    $root64 = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($Root))
    foreach ($profile in ($ProfilePaths | Select-Object -Unique)) {
        $document = Get-HciProfileDocument $profile
        $text = Remove-HciProfileBlock $document.Text
        $newline = if ($text.Contains("`r`n") -or -not $text) { "`r`n" } else { "`n" }
        if ($text -and -not $text.EndsWith("`n")) { $text += $newline }
        $block = @'
# BEGIN herdr-codex-images-installer
if ($env:HC_TERMINAL_ID) {
    $__hciRoot = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('__ROOT64__'))
    $__hciStatePath = Join-Path $__hciRoot 'install.json'
    if (Test-Path -LiteralPath $__hciStatePath) {
        $__hciState = [IO.File]::ReadAllText($__hciStatePath) | ConvertFrom-Json
        $__hciBin = Join-Path $__hciRoot ('versions\' + $__hciState.version + '\codex\bin')
        if (Test-Path -LiteralPath (Join-Path $__hciBin 'codex.exe')) { $env:Path = $__hciBin + ';' + $env:Path }
    }
}
# END herdr-codex-images-installer
'@
        $block = $block.Replace('__ROOT64__',$root64).Replace("`r`n","`n").Replace("`n",$newline)
        $candidate = $text + $block + $newline
        $tokens=$null; $errors=$null
        $null = [Management.Automation.Language.Parser]::ParseInput($candidate,[ref]$tokens,[ref]$errors)
        if ($errors.Count) { throw "Profile syntax error; unchanged: $profile" }
        $documentsToWrite += [pscustomobject]@{ Document=$document; Text=$candidate }
    }
    $shortcut = if (-not $NoShortcut) { Join-Path $ShortcutDirectory 'Herdr Images.lnk' } else { $null }
    if ($shortcut) { Initialize-HciShortcut }
    if ($shortcut -and (Test-Path -LiteralPath $shortcut)) {
        $link = [HciWindowsShortcutV1]::Load($shortcut)
        if ($link[0] -ne $script:HciOwner -or -not $link[1].Contains($Root + '\bootstrap.ps1')) { throw 'Unmanaged Herdr Images shortcut exists.' }
    }
    Test-HciRuntime $Payload
    $destination = Assert-HciChild $Root (Join-Path $Root ('versions\' + $Version))
    if (Test-Path -LiteralPath $destination) {
        if ([IO.File]::ReadAllText((Join-Path $destination 'ARCHIVE.sha256')).Trim() -ine $ArchiveHash) { throw 'Installed version differs; refusing replacement.' }
        Test-HciRuntime $destination
    } else {
        [IO.Directory]::CreateDirectory((Join-Path $Root 'versions')) | Out-Null
        [IO.File]::WriteAllText((Join-Path $Payload 'ARCHIVE.sha256'),$ArchiveHash)
        Move-Item -LiteralPath $Payload -Destination $destination
    }
    [IO.Directory]::CreateDirectory((Join-Path $Root 'backups')) | Out-Null
    $appHome = Join-Path $Root 'app-home'
    if (-not (Test-Path -LiteralPath $appHome)) {
        [IO.Directory]::CreateDirectory($appHome) | Out-Null
        if (-not $SourceConfig) {
            $SourceConfig = if ($env:HERDR_APP_HOME) { $env:HERDR_APP_HOME } elseif ($env:XDG_CONFIG_HOME) { Join-Path $env:XDG_CONFIG_HOME 'herdr-app' } else { Join-Path $env:USERPROFILE '.config\herdr-app' }
        }
        foreach ($name in @('settings.json','keys.json','shared.json','view.json','window.json','seen.json','installed.json','layouts','mods','frame','data','themes')) {
            $source = Join-Path $SourceConfig $name
            if (Test-Path -LiteralPath $source) { Copy-Item -LiteralPath $source -Destination (Join-Path $appHome $name) -Recurse }
        }
    }
    $bootstrap = @'
# HerdrCodexImages managed entry v1
param([string]$Command='open',[Parameter(ValueFromRemainingArguments=$true)][string[]]$Rest)
$ErrorActionPreference='Stop'
$state=[IO.File]::ReadAllText((Join-Path $PSScriptRoot 'install.json')) | ConvertFrom-Json
if ($state.owner -ne 'herdr-codex-images/windows/v1' -or $state.version -notmatch '^v[0-9][A-Za-z0-9.-]*$') { throw 'Invalid installation state.' }
& (Join-Path $PSScriptRoot ('versions\'+$state.version+'\tools\windows-manager.ps1')) -Root $PSScriptRoot -Command $Command -Rest $Rest
'@
    [IO.File]::WriteAllText((Join-Path $Root 'bootstrap.ps1'),$bootstrap,[Text.UTF8Encoding]::new($true))
    $cmd = "@echo off`r`nrem HerdrCodexImages managed entry v1`r`npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File `"%~dp0bootstrap.ps1`" %*`r`n"
    [IO.File]::WriteAllText((Join-Path $Root 'herdr-images.cmd'),$cmd,[Text.Encoding]::ASCII)
    $previous = if ($old -and $old.version -ne $Version) { $old.version } elseif ($old) { $old.previous } else { $null }
    $state = [ordered]@{ owner=$script:HciOwner; version=$Version; previous=$previous; profiles=@($ProfilePaths); shortcut=$shortcut }
    $written = @()
    try {
        foreach ($change in $documentsToWrite) {
            $written += $change.Document
            Save-HciProfile $Root $change.Document $change.Text
        }
        Set-HciState $Root $state
    } catch {
        $installError = $_
        foreach ($document in $written) {
            if ($document.Existed) {
                $current = [IO.File]::ReadAllBytes($document.Path)
                if ([Convert]::ToBase64String($current) -ne [Convert]::ToBase64String($document.Bytes)) { [IO.File]::WriteAllBytes($document.Path,$document.Bytes) }
            } elseif (Test-Path -LiteralPath $document.Path) { Remove-Item -LiteralPath $document.Path }
        }
        throw $installError
    }
    if ($shortcut) {
        [IO.Directory]::CreateDirectory($ShortcutDirectory) | Out-Null
        $arguments = '-NoLogo -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $Root + '\bootstrap.ps1" open'
        [HciWindowsShortcutV1]::Save($shortcut,(Get-HciPowerShell),$arguments,$env:USERPROFILE,(Join-Path $destination 'herdr\herdr-app.exe'),$script:HciOwner)
    }
}
