# Distribution

The macOS Apple Silicon and Windows x64 previews contain versioned prebuilt archives,
SHA256SUMS, and one-command installers. They include patched Herdr/Codex, official
Herdr core, Codex companions/resources, and upstream licenses/notices.

Installation is per-user and side-by-side. First-run app config is copied;
existing projects, the original app, and core sessions are preserved. Cached
archives and stripped release symbols reduce download and install time.
`doctor`, `update`, `rollback`, and `uninstall` need no compiler or Python.

The Mac app is locally ad-hoc signed rather than Apple-notarized; patched Windows
executables are unsigned. Windows packages retain ConPTY resources and application-local
VC++ runtime DLLs. Hosted native builds, notarization/code signing and a plugin
marketplace entry remain future work. Source patches remain independently usable.

Maintainers use `tools/package_macos.py` or `tools/package_windows.py` with explicitly
supplied validated binaries.
No user app homes, credentials, sessions or project files enter the archives.
CI tests installer preservation and recovery using disposable homes.

Design references: [Codex HUD](https://github.com/konnga/codex-hud),
[Herdr Islands](https://github.com/Yofukashiya/herdr-islands), and
[Herdr Reader](https://github.com/giacolees/herdr-reader).
