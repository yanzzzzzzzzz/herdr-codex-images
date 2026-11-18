# Distribution plan

This initial revision is a source preview. There is no published runtime archive,
marketplace entry, or one-command binary installer yet.

The intended distribution keeps independent native components behind one project:

- A plugin/marketplace entry can provide setup, doctor, update, and uninstall skills.
- Versioned GitHub Releases can hold platform archives, a compatibility manifest,
  SHA-256 values, source patches, and upstream notices.
- Setup should allow Codex-only, Herdr-only, or the validated combined installation.
- Native binaries should be staged separately, checked, and backed up before activation.
  Existing official installations and active sessions should remain recoverable.
- Updates must check base-version compatibility; application state and credentials
  must not be included in release archives.

Current distribution references:

- [Codex HUD](https://github.com/konnga/codex-hud): marketplace entry, setup/doctor
  skills, managed runtime, and separate release archives/checksums. Its own runtime
  does not replace the official Codex binary; this project's native patch deployment
  would need to be clearly disclosed as a different operation.
- [Herdr Islands](https://github.com/Yofukashiya/herdr-islands): shell/PowerShell
  installers, component selection, validation, and settings-preserving updates.
- [Herdr Reader](https://github.com/giacolees/herdr-reader): a mod plus a rendering
  helper, with images displayed in a separate reader pane.

These are design references, not dependencies or third-party installers run by this repository.
