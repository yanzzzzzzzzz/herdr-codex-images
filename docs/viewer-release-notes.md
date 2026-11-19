The standalone Rust viewer keeps the official Herdr desktop and official Codex CLI.
It installs one desktop mod, a versioned helper and a separate **Codex + Images**
menu entry. Image replies appear automatically in a pane beside that Codex session.

The release binaries are built from the tagged source on GitHub-hosted runners.
`viewer-provenance.jsonl` is a GitHub/Sigstore verification bundle covering the
binaries, fixed-version installers, source manifests and CycloneDX dependency lists.
New releases are immutable. Installers verify fixed hashes and build provenance
before executing the viewer. `update --version TAG` refuses mutable releases,
unexpected source identities and invalid provenance, and requires GitHub CLI.

The operating-system binaries are not publisher-signed or notarized. Provenance
establishes build origin; it is not an independent code audit or a promise of no bugs.

Automatic previews use an explicit full thread ID in the launched Codex footer,
then validate the exact rollout's identity. No other conversation contents are read.
This preview supports local images linked in completed Codex replies inside that
session's workspace. Embedded tool images, remote workspaces, Mermaid and LaTeX
are not implemented. The full published usage and security boundaries are in
`viewer/README.md` and `SECURITY.md`.

The older native Herdr/Codex patch releases remain a separate experimental route;
this provenance does not retroactively cover those releases.
