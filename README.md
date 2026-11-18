# Herdr Codex Images

[繁體中文](README.zh-TW.md)

Inline image artifacts in Codex CLI, with clickable original-image inspection in Herdr.
One repository, two independently managed native components.

**Status: binary preview for macOS Apple Silicon.** Prebuilt Herdr, Codex and core
are available through GitHub Releases. Windows remains source-only. This is an
independent project, not an official Herdr or OpenAI release.

## Install on a Mac

Run one command in Terminal:

```sh
curl -fsSL https://github.com/yanzzzzzzzzz/herdr-codex-images/releases/download/v0.1.0-preview.1/install.sh | sh
```

The installer downloads a checksum-verified prebuilt archive and opens **Herdr Images**.
It needs no compiler, Git, Python, sudo, existing Herdr, or existing Codex installation.
The preview app is locally signed, not an Apple-notarized release.

Your original Herdr app, projects, credentials and running terminals are preserved.
On first install, settings and spaces are copied into the new app's separate config;
subsequent changes are independent. Existing core sessions remain available.
New Herdr shells select the bundled Codex through a backed-up, managed `.zshrc`
block. Other shells retain their existing Codex. Start a new Codex process to use it.

```sh
~/.local/bin/herdr-images doctor
~/.local/bin/herdr-images update
~/.local/bin/herdr-images rollback
~/.local/bin/herdr-images uninstall
```

Uninstall removes only managed links and the shell block, keeping backups and settings.
See [installation details](docs/installation.md) for paths, offline installation and recovery.

## Features

- **Codex:** preview existing local raster images linked in completed assistant
  replies, including Markdown images, file links, and code-formatted image paths.
  Multiple images appear below the reply in source order, with duplicate paths removed.
- **Herdr:** click a terminal image to open a separate, resizable preview. Compatible
  Codex references load the original from the machine running that terminal.
- Fit / `0`, actual pixels / `1`, `+` / `-`, scrolling, drag-to-pan, and `Esc` to close.
- Keep original reply text searchable and copyable. Preview keys do not enter Codex.

Codex previews also work independently in compatible graphics terminals. Herdr can
inspect transmitted terminal pixels independently; full original-file inspection
requires the reference emitted by the Codex component.

## Compatibility

| Component | Pinned upstream | Validated environment |
| --- | --- | --- |
| Herdr app | `v0.1.16` | Windows x64, macOS Apple Silicon |
| Codex CLI | `rust-v0.169.1` | macOS Apple Silicon |
| Cross-machine originals | Existing Herdr core connection | Windows client → macOS host |

Exact commits and patch SHA-256 values are in [manifest.json](manifest.json).
Other platforms and upstream versions have not been validated. Prebuilt binaries
are release assets, separate from Git source files.

## Use the source patches

Python 3.9+ and Git are required for the patch tool. It checks the patch hash, exact
upstream commit, and clean checkout before changing files. It does not install apps,
change shell profiles, or restart running programs.

```sh
git clone https://github.com/yanzzzzzzzzz/herdr-codex-images.git
cd herdr-codex-images
```

Choose either component:

- [Build the Herdr component](components/herdr/README.md)
- [Build the Codex component](components/codex/README.md)

Run `python tools/patch_component.py --validate` to verify both bundled patches.
Use `--apply` only with a dedicated checkout. Without that flag the tool only checks.

## Limits and validation

- Image files must exist on the machine running Codex. HTTP(S) images are not downloaded.
- Replies preview at most eight unique images; missing or undecodable files retain
  their text links. Fenced code examples do not trigger previews.
- Reply previews are bounded to about one third of the terminal height, up to 12 rows.
  Use original-image inspection for full detail.
- CLI decoding retains the upstream 32 MiB limits. Herdr original-file loading has a
  32 MiB file limit and a 64 MiB decoded pixel budget.
- Opening a new Codex chat inside an old process does not load a different executable.
  Start a new process after deploying a build; existing sessions can remain open.

See [validation](docs/validation.md), [architecture](docs/architecture.md), and
[distribution plan](docs/distribution.md). The underlying terminal graphics support
already exists upstream; see [Codex #29451](https://github.com/openai/codex/issues/29451).
This project extends ordinary reply-file previews and Herdr original-image interaction.

## Development

```sh
python -m unittest discover -s tests -v
python tools/patch_component.py --validate
```

The packaging helper uses only Python's standard library. Upstream applications
retain their own Rust and native build dependencies.

## License

Apache-2.0. See [LICENSE](LICENSE), [NOTICE](NOTICE), and [upstream notices](licenses/).
