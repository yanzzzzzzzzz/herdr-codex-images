# Distribution

The macOS Apple Silicon preview release contains a versioned prebuilt archive,
SHA256SUMS, and a one-command installer. It includes patched Herdr/Codex, official
Herdr core, Codex companions/resources, and upstream licenses/notices.

Installation is per-user and side-by-side. First-run app config is copied;
existing projects, the original app, and core sessions are preserved. Cached
archives and stripped release symbols reduce download and install time.
`doctor`, `update`, `rollback`, and `uninstall` need no compiler or Python.

This is a locally ad-hoc signed preview, not an Apple-notarized release.
Windows prebuilt packages, hosted native builds, notarization and a plugin
marketplace entry remain future work. Source patches remain independently usable.

Maintainers use `tools/package_macos.py` with explicitly supplied validated binaries.
No user app homes, credentials, sessions or project files enter the archives.
CI tests installer preservation and recovery using disposable homes.

Design references: [Codex HUD](https://github.com/konnga/codex-hud),
[Herdr Islands](https://github.com/Yofukashiya/herdr-islands), and
[Herdr Reader](https://github.com/giacolees/herdr-reader).
