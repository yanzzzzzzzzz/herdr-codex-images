# Windows PowerShell 5.1+; no admin, compiler, Git, Python, reset or process stop.
[CmdletBinding()]
param(
    [string]$Version = 'v0.1.0-preview.3',
    [string]$Archive,
    [string]$Checksums,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'Programs\herdr-codex-images'),
    [string]$CacheRoot = (Join-Path $env:LOCALAPPDATA 'Caches\herdr-codex-images'),
    [string]$SourceConfig,
    [string[]]$ProfilePaths,
    [string]$ShortcutDirectory = ([Environment]::GetFolderPath('Programs')),
    [switch]$NoLaunch,
    [switch]$NoShortcut
)
& {
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
function Get-HciSha256([string]$Path) {
    $stream = [IO.File]::OpenRead([IO.Path]::GetFullPath($Path))
    $sha = [Security.Cryptography.SHA256]::Create()
    try { [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant() }
    finally { $sha.Dispose(); $stream.Dispose() }
}
$nativeArchitecture = if ($env:PROCESSOR_ARCHITEW6432) { $env:PROCESSOR_ARCHITEW6432 } else { $env:PROCESSOR_ARCHITECTURE }
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or $nativeArchitecture -ne 'AMD64') { throw 'This release requires Windows x64.' }
if ($Version -notmatch '^v[0-9][A-Za-z0-9.-]*$') { throw 'Invalid release tag.' }
$InstallRoot = [IO.Path]::GetFullPath($InstallRoot)
if ($InstallRoot.TrimEnd('\') -eq [IO.Path]::GetPathRoot($InstallRoot).TrimEnd('\')) { throw 'Use a dedicated installation directory, not a drive root.' }
$InstallRoot = $InstallRoot.TrimEnd('\')
if (Test-Path -LiteralPath $InstallRoot) {
    if ((Get-Item -LiteralPath $InstallRoot -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Install root must not be a junction or symbolic link.' }
}
New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
$lock = $null
$stage = Join-Path $InstallRoot ('.install-' + [guid]::NewGuid().ToString('N'))
try {
    $lock = [IO.File]::Open((Join-Path $InstallRoot '.install.lock'), [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    New-Item -ItemType Directory -Path $stage | Out-Null
    $asset = "herdr-codex-images-$Version-windows-x64.zip"
    if (-not $Archive) {
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        $cache = Join-Path $CacheRoot $Version
        New-Item -ItemType Directory -Path $cache -Force | Out-Null
        $url = "https://github.com/yanzzzzzzzzz/herdr-codex-images/releases/download/$Version"
        $Checksums = Join-Path $stage 'SHA256SUMS'
        Invoke-WebRequest -UseBasicParsing -Uri "$url/SHA256SUMS" -OutFile $Checksums
        $Archive = Join-Path $cache $asset
        if (-not (Test-Path -LiteralPath $Archive -PathType Leaf)) {
            Invoke-WebRequest -UseBasicParsing -Uri "$url/$asset" -OutFile "$Archive.part"
            Move-Item -LiteralPath "$Archive.part" -Destination $Archive
        }
    }
    if (-not $Checksums) { throw 'Offline installation requires -Archive and -Checksums.' }
    $matches = @([IO.File]::ReadAllLines([IO.Path]::GetFullPath($Checksums)) | Where-Object { $_ -match ('^[a-fA-F0-9]{64}  ' + [regex]::Escape($asset) + '$') })
    if ($matches.Count -ne 1) { throw 'Missing or ambiguous archive checksum.' }
    $expected = $matches[0].Substring(0, 64)
    if ((Get-HciSha256 $Archive) -ine $expected) { throw "Checksum mismatch; remove the cached archive before retrying: $Archive" }

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($Archive))
    try {
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName.Replace('\', '/')
            if ($name -notmatch '^payload/' -or $name -match '(^|/)\.\.(/|$)|:|^/' -or (($entry.ExternalAttributes -shr 16) -band 0xF000) -eq 0xA000) { throw "Unsafe archive entry: $name" }
            $target = [IO.Path]::GetFullPath((Join-Path $stage $name))
            if (-not $target.StartsWith($stage + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Archive escaped the staging directory.' }
        }
    } finally { $zip.Dispose() }
    [IO.Compression.ZipFile]::ExtractToDirectory([IO.Path]::GetFullPath($Archive), $stage)
    $payload = Join-Path $stage 'payload'
    if ([IO.File]::ReadAllText((Join-Path $payload 'VERSION')).Trim() -ne $Version) { throw 'Archive version mismatch.' }
    foreach ($line in [IO.File]::ReadAllLines((Join-Path $payload 'FILES.sha256'))) {
        if ($line -notmatch '^([a-f0-9]{64})  (.+)$') { throw 'Malformed payload checksum.' }
        $hash = $Matches[1]; $relative = $Matches[2]
        $file = [IO.Path]::GetFullPath((Join-Path $payload $relative))
        if (-not $file.StartsWith($payload + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe checksum path.' }
        if ((Get-HciSha256 $file) -ine $hash) { throw "Payload mismatch: $relative" }
    }
    . (Join-Path $payload 'tools\windows-common.ps1')
    Install-HciWindows -Root $InstallRoot -Payload $payload -Version $Version -ArchiveHash $expected -SourceConfig $SourceConfig -ProfilePaths $ProfilePaths -ShortcutDirectory $ShortcutDirectory -NoShortcut:$NoShortcut
    Write-Host "Installed Herdr Images $Version. Original Herdr, projects and running sessions are preserved."
    Write-Host "Manage: & `"$InstallRoot\herdr-images.cmd`" doctor"
    if (-not $NoLaunch) {
        $shell = Get-HciPowerShell
        Start-Process -FilePath $shell -WindowStyle Hidden -ArgumentList @('-NoLogo','-NoProfile','-ExecutionPolicy','Bypass','-File',('"' + $InstallRoot + '\bootstrap.ps1"'),'open') | Out-Null
    }
} finally {
    if ($stage -and (Test-Path -LiteralPath $stage)) {
        $resolvedStage = [IO.Path]::GetFullPath($stage)
        if (-not $resolvedStage.StartsWith($InstallRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Unsafe cleanup target.' }
        if ((Get-Item -LiteralPath $resolvedStage -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Refusing recursive cleanup of a link.' }
        $directories = [Collections.Generic.Stack[string]]::new()
        $directories.Push($resolvedStage)
        while ($directories.Count) {
            foreach ($child in [IO.Directory]::EnumerateFileSystemEntries($directories.Pop())) {
                $attributes = [IO.File]::GetAttributes($child)
                if ($attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Retaining staging directory because it contains a link; no linked files were deleted.' }
                if ($attributes -band [IO.FileAttributes]::Directory) { $directories.Push($child) }
            }
        }
        Remove-Item -LiteralPath $resolvedStage -Recurse -Force
    }
    if ($lock) { $lock.Dispose() }
}
}
