# macOS preview installation

Supports macOS Apple Silicon; validated on a Mac mini. This preview uses local
ad-hoc signing, not Apple notarization. Windows remains source-only.

```sh
curl -fsSL https://github.com/yanzzzzzzzzz/herdr-codex-images/releases/download/v0.1.0-preview.1/install.sh | sh
```

The installer opens Herdr Images. For installation without opening a window,
download `install.sh` and run `sh install.sh --no-open`.

## What changes

| Path | Purpose |
| --- | --- |
| `~/Applications/Herdr Images.app` | Link to the separate app |
| `~/.local/share/herdr-codex-images/versions/<tag>` | Versioned app and runtime |
| `~/.local/share/herdr-codex-images/current` | Active version link |
| `~/.local/share/herdr-codex-images/previous` | Rollback version after an update |
| `~/.local/share/herdr-codex-images/app-home` | Separate settings and spaces |
| `~/.local/share/herdr-codex-images/backups` | Shell-profile snapshots |
| `~/.local/bin/herdr-images` | Management command |
| `${ZDOTDIR:-$HOME}/.zshrc` | One managed block for new Herdr shells |
| `~/Library/Caches/herdr-codex-images/<tag>` | Verified reusable download |

The original Herdr app/config, `.codex` login/chat state and projects are never
reset or replaced. The installer never stops a core, terminal, agent or app.
On first install it copies existing Herdr settings, custom mods/themes and space
layout into its separate app home. It does not continuously synchronize them.
Both apps connect to the normal Herdr core, so existing terminals remain available.
The supplied official core is a fallback; an existing `~/.local/bin/hc` takes priority.

New Herdr zsh shells use the image-enabled Codex; normal shells retain their
existing Codex. Other shell startup files are not edited automatically. Existing
Codex processes retain their executable until restarted.

## Manage

```sh
~/.local/bin/herdr-images doctor
~/.local/bin/herdr-images open
~/.local/bin/herdr-images update
~/.local/bin/herdr-images rollback
~/.local/bin/herdr-images uninstall
```

`doctor` checks installed hashes, app signature, executables and the search
companion without starting an agent or making model requests. Updates retain
the previous version and app settings. Reopen the app when convenient to load
new native code; existing terminals continue running.

Uninstall removes only managed app/command links, the active-version link and
its shell block, preserving later unrelated edits. Settings, backups, downloads
and version folders remain recoverable. An old profile is never restored wholesale
over newer edits.

## Offline install

Download the installer, archive and checksums from the same release:

```sh
sh install.sh --archive ./herdr-codex-images-v0.1.0-preview.1-macos-arm64.tar.gz \
  --checksums ./SHA256SUMS
```

Offline and online installation use identical checksum/path checks. An unrelated
app or command already using the destination name is not overwritten. Invalid
archives never become the active runtime.

## Build release assets

Maintainers run `python3 tools/package_macos.py --help` on an arm64 Mac. Supply
a validated Herdr app, the complete Codex platform directory, official Herdr Core.app,
its license, a version tag and an empty output location. The release copy of Codex
is stripped of debug/local symbol metadata and re-signed; the original is unchanged.
Version/help/resume-help, search companion, app/core signatures and archive hashes
are checked before producing assets. Binaries are separate from Git source.
