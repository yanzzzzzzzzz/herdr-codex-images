# Windows x64 installation

Open Windows PowerShell 5.1 or PowerShell 7 and run:

```powershell
irm https://github.com/yanzzzzzzzzz/herdr-codex-images/releases/download/v0.1.0-preview.2/install.ps1 | iex
```

The installer downloads a prebuilt ZIP, verifies SHA-256 and file hashes, creates
the separate **Herdr Images** Start menu entry, and opens the app. No administrator,
Rust, Zig, Git, Python or source compilation is needed. The package includes the
official core, full Codex companion/resource bundle and application-local VC++ runtime
DLLs. Patched executables are an independently built preview, not Authenticode-signed.

## Preserve your existing setup

The original Herdr app, projects, Codex login/chat state and all running core
sessions are retained. The installer never stops a program or resets a core.
On first installation, existing Herdr settings, custom mods/themes and space layout
are copied into a separate app home. App preferences and custom mod files are
managed separately. Core-managed space layouts and terminals remain shared, so
both apps can attach to the existing sessions without recreating them.

The installer backs up and adds one managed block to each PowerShell edition's
current-user, all-hosts profile. Only new shells with `HC_TERMINAL_ID` select the
bundled Codex. Ordinary shells retain their existing Codex. Existing terminals
keep their current PATH and existing Codex processes keep their executable;
open a new Herdr terminal to use the image-enabled Codex.
Other shells, such as cmd.exe, do not have startup files edited automatically.
This installs the local Windows components; remote hosts need their matching
Codex component separately.

The Windows execution policy, registry PATH and original Herdr Start menu entry
are not changed. Script launchers use a process-scoped execution policy.

## Installed paths

| Path | Purpose |
| --- | --- |
| `%LOCALAPPDATA%\Programs\herdr-codex-images` | Dedicated installation root |
| `versions\<tag>` under that root | Retained versioned executables |
| `install.json` under that root | Active/previous version and managed paths |
| `app-home` under that root | Separate app settings and spaces |
| `backups` under that root | Exact profile snapshots and previous version state |
| `herdr-images.cmd` under that root | Management entry |
| `%LOCALAPPDATA%\Caches\herdr-codex-images\<tag>` | Reusable verified download |
| Documents\WindowsPowerShell\profile.ps1 | Windows PowerShell integration |
| Documents\PowerShell\profile.ps1 | PowerShell 7 integration |
| Current-user Start menu\Herdr Images.lnk | Separate app shortcut |

The actual Windows Documents location is respected, including redirection to OneDrive.
Profile encodings, Unicode paths and existing unrelated content are preserved.

## Manage and recover

```powershell
$images = "$env:LOCALAPPDATA\Programs\herdr-codex-images\herdr-images.cmd"
& $images doctor
& $images open
& $images update
& $images rollback
& $images uninstall
```

`doctor` verifies runtime hashes, versions, help and search without starting a model.
An update installs into a new version directory; rollback switches the version state.
Reopen the app when convenient to use new native code. Running processes and their
version directories remain intact, including during uninstall.

Uninstall removes only managed launchers, the owned shortcut and its profile blocks,
preserving unrelated profile edits made after installation. Settings, backups,
downloads and version directories stay available for recovery. It does not restore
an old profile wholesale over newer changes or stop existing sessions.

## Offline installation

Download the ZIP, `SHA256SUMS` and `install.ps1` from the same release:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 `
  -Archive .\herdr-codex-images-v0.1.0-preview.2-windows-x64.zip `
  -Checksums .\SHA256SUMS
```

Add `-NoLaunch` for installation without opening a window. Corrupt or unsafe archives
are rejected before activation. Unrelated files at the managed entry/shortcut paths
are not overwritten. Updates use cached downloads after verifying their hashes.

Maintainers package explicitly supplied validated binaries with
`python tools/package_windows.py --help`. The Unicode shortcut helper is compiled
at packaging time; the user's installer only loads the verified DLL.
