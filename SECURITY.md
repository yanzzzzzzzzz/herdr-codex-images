# Security and trust boundaries

## Current routes

The recommended standalone Rust viewer does not replace Herdr or Codex. The older
native patch previews modify both programs and have a larger trust and maintenance
surface. Their existing releases are not retroactively attested or made immutable.
The current source retires the legacy updater that executed scripts from `main`;
copies already inside old published archives are unchanged. Do not use those old
update commands. Prefer an explicit standalone viewer release.

No route is an assertion that the software is free of vulnerabilities. Tests,
hashes, publisher signatures and build attestations establish different facts;
none is an independent code audit. Patched legacy binaries and new viewer binaries
are not OS publisher-signed/notarized. No certificate or external audit is claimed.

## Release evidence

New viewer releases use `.github/workflows/viewer-release.yml`. Windows, macOS ARM
and Linux x64 helpers are built and tested from the tagged source on GitHub-hosted
runners with a locked Cargo dependency graph and commit-pinned Actions. Build jobs
have read-only repository permissions. A separate job reads the artifacts and
generates GitHub/Sigstore build provenance before publishing the complete release.
Dependency build code is not run in that signing job.

The release contains raw binaries, fixed-version installers, source manifests,
CycloneDX dependency inventories and `viewer-provenance.jsonl`. A dependency list
is not a vulnerability scan. Repository secret scanning/push protection and
Dependabot security updates are enabled. GitHub's immutable-release setting was
enabled for future releases; existing legacy assets are deliberately unchanged.

The installers verify an exact binary hash, then its build certificate using an
exact official GitHub CLI verifier archive pinned by SHA-256. Verification checks
the repository, repository ID, workflow, tag, source commit and hosted-runner policy.
No payload is executed after a failed check. The first bootstrap script still
requires trust in the repository and GitHub HTTPS delivery; review it or verify
its own attestation with an independently obtained verifier before running it.

The Rust `update --version TAG` path additionally rejects mutable/draft releases
and requires GitHub CLI. It never executes a script from a mutable branch and
never silently falls back from failed provenance verification to hashes alone.
Do not interpret an attestation as protection against malicious reviewed source,
an authorized malicious publisher, compromised dependencies or a compromised OS.

## Local permissions and data

The helper and mod run as the current user; they are not sandboxed. No admin,
registry PATH edit, shell-profile edit, credential import or global agent instruction
change is needed. The official Codex process still has its normal permissions and
account behavior; the viewer does not authenticate to OpenAI or make model calls.

| Operation | Reads | Writes / network |
| --- | --- | --- |
| Install desktop | Its own binary and existing viewer/menu config | Owned mod, versioned helper, one menu entry, backups |
| Launch Codex + Images | Exact source terminal's visible footer; matching rollout | Per-terminal state and normalized image cache; starts installed Codex |
| Show an image | Explicit local file | Local PNG cache and viewer state |
| Automatic preview | Completed final-answer paths inside the bound workspace | Local cache; no image URL downloads |
| Open original | Revalidated selected image | Starts the OS image viewer after an explicit click |
| Update | Explicit immutable release and provenance | GitHub/Sigstore verification traffic; new owned helper/mod version |

The helper does not open `auth.json`, API-key stores or unrelated conversation
contents. Codex itself reads its account as usual. Cached images and original
paths can be sensitive and are not encrypted by this project. They are retained
after uninstall along with backups. Delete them through your normal filesystem
tools when no viewer uses them. The official Herdr's and Codex's own network,
telemetry and remote connection behavior remains governed by those projects.

Images have file/decoder/asset limits documented in `viewer/README.md`. Remote URLs,
UNC paths and remote app-server workspaces are not loaded. No arbitrary command
strings or tool output are evaluated as image-rendering code. File paths are passed
as separate process arguments. The terminal footer and local installation state
are trusted local inputs; this is not a sandbox against malicious local agents.

## Reporting

Use GitHub's private vulnerability reporting / **Security → Report a vulnerability**
for this repository. Do not post credentials, private conversation contents or
private images in public issues. Include the release tag, OS and a minimal
fictional reproducer. No response-time SLA or bug bounty is promised.
