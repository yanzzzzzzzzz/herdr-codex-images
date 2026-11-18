# Validation record

Recorded on 2026-11-18 before initial publication. These are targeted local validation
results, not a claim of a full upstream CI run or every-platform support.

## Herdr: Windows x64

- Terminal tests: **82 passed, 1 ignored**.
- Main application unit tests: **448 passed, 2 ignored**, single-threaded.
- The ignored remote-original test was separately configured and passed over an
  existing Windows-to-macOS Herdr connection: a 2048×1024, 7,173,553-byte PNG decoded
  identically pixel for pixel after chunked transfer.
- Original display, actual-size zoom, two-axis scroll, drag-to-pan, fallback, parent
  close, Escape, and absence of terminal key forwarding were tested in GPUI test windows.
- The other ignored test requires an isolated running core with two app viewers.
- Release build and installed executable SHA-256 comparison passed.

Commands used, with toolchain paths configured for the build machine:

```sh
cargo +1.95.0 test --locked --bin herdr-app --config 'profile.dev.package."*".opt-level=0' --jobs 2 terminal::
cargo +1.95.0 test --locked --bin herdr-app --config 'profile.dev.package."*".opt-level=0' --jobs 2 -- --test-threads=1 --nocapture
cargo +1.95.0 test --locked --bin herdr-app --config 'profile.dev.package."*".opt-level=0' --jobs 2 remote_original_matches -- --ignored --nocapture
cargo +1.95.0 build --release --locked --jobs 2
```

The remote test needs `HERDR_PREVIEW_REMOTE_TEST_MACHINE`,
`HERDR_PREVIEW_REMOTE_TEST_URI`, and `HERDR_PREVIEW_LOCAL_TEST_FILE`.
An initial sandboxed full run hit a Windows handle restriction; the subsequent
single-threaded run outside that restriction passed.

## Herdr: macOS ARM64 installation from GitHub

On 2026-11-18, a fresh clone of the public integration repository was used to
validate both patch hashes and apply them to clean, pinned upstream checkouts.
All five packaging tests passed on Python 3.9.6.

- Herdr terminal tests: **86 passed, 1 ignored**.
- Full application unit tests: **496 passed, 3 ignored**, single-threaded.
- Release build: passed with Rust 1.95.0 and Zig 0.16.0.
- Existing Herdr app/state were backed up before the user-authorized full reset.
- The app bundle was installed, locally signed with upstream entitlements, and
  passed `codesign --verify --deep --strict`.
- The installed desktop app opened without reported errors. A dedicated terminal
  displayed an 800×400 PNG through Kitty graphics; its first-run welcome window
  remained visible over part of the fixture. This was not a real-pointer click test.

The initial full test run failed seven unchanged file-watcher tests because system
Git required a full-Xcode license. Re-running with working Homebrew Git and CLT
passed all non-ignored tests. Test build-time dylibs needed debug information and
`build-override.strip="none"` on this macOS; see the component build notes.

The Codex release build reused an existing cache only after verifying the exact
upstream HEAD, changed-file set, and byte-for-byte contents of all ten modified
files against the fresh GitHub-patched checkout. The full platform bundle,
including companion executables and resources, was installed separately and checked.
Version/help/resume-help, companion search, and Herdr-only launcher resolution passed.
No paid model request was made during this installation smoke test.

## Codex: macOS ARM64

- Assistant-image parsing: 1 test passed, also included in the message tests below.
- Transcript view: **274 passed**.
- History messages: **16 passed**.
- Custom terminal: **19 passed**.
- Total: **309 distinct related tests passed**.
- Original draft-image integration: 2 tests passed during the preceding implementation.
- Final release build: passed. Version, help, resume help, companion search tool,
  and separate official/custom launcher resolution were checked.

```sh
cargo +1.95.0 test --locked --profile dev-small -p codex-tui --lib --jobs 2 assistant_images
cargo +1.95.0 test --locked --profile dev-small -p codex-tui --lib --jobs 2 transcript_view::
cargo +1.95.0 test --locked --profile dev-small -p codex-tui --lib --jobs 2 history_cell::messages
```

The already-built test executable was also run with `custom_terminal:: --test-threads=2`.
The equivalent Cargo invocation is:

```sh
cargo +1.95.0 test --locked --profile dev-small -p codex-tui --lib --jobs 2 custom_terminal:: -- --test-threads=2
cargo +1.95.0 build --locked --release -p codex-cli --bin codex --jobs 2
```

Rust formatting, patch whitespace, and reverse-application checks passed. The lockfile
audit found only 173 workspace version updates, with zero external package changes.
No paid model conversation or input into an active user conversation was required.
Real third-party GUI end-to-end clicking is outside this validation record.

## Publication checks

Public patches use generic test-fixture paths. Machine addresses, deployment paths,
personal screenshots, authentication files, and private installation logs are excluded.
The public patch variants are checked against the exact upstream base indexes.
Packaging-tool tests cover hash validation, version mismatch, dirty checkouts, repeated
application, and actual application to a disposable Git repository.
All five packaging-tool tests and both bundled patch-hash checks passed before publication.
No application or model session was started for these packaging checks.

## Prebuilt installer: v0.1.0-preview.1

The macOS Apple Silicon preview is a side-by-side installation. It never resets
the existing app/config, project files, credentials or core sessions.

- `sh -n install.sh` and `sh -n tools/herdr-images.sh`: passed.
- `python3 -m unittest discover -s tests -v` on macOS 27.2.1 / Python 3.9.6:
  **14 passed** (nine installer regressions plus five source-tool tests).
- Regression coverage includes unchanged original projects/settings, dotfiles
  symlinks, repeated install, updates, rollback, later shell edits on uninstall,
  corrupt archives, traversal paths, unrelated app collisions and runtime tampering.
- The full runtime archive installed offline in **6.22 seconds**, excluding download;
  doctor and uninstall passed, with fixture project/config hashes unchanged.
- Installation directly from the public GitHub Release, including the download and
  app-open request, took **23.00 seconds** on the test Mac/network.
- Repeated installation with the verified cached archive took **6.37 seconds**.
- Both pre-existing core terminals stayed live. Original app/settings/auth hashes
  were unchanged, and the previous shell profile remained intact.
- The separate app opened with no reported errors. A new real Herdr shell resolved
  to the bundled Codex; its independent 800×400 PNG fixture rendered visibly.
- No model request or real-pointer click was used. Native image-interaction tests
  remain the interaction evidence described above.

The archive is 174,313,825 bytes. Its Codex binary was reduced from 378,699,336 to
279,630,592 bytes by stripping release-copy symbol/debug metadata and re-signing.
Version/help/resume-help, companion search, app/core signatures and archive/file
hashes were checked. Network timings are measurements, not a speed guarantee.

Release binaries derive from source commit `a0e8dc60e3bce3fbbfb7d99dae44080a98afaf89`
and the unchanged pinned native patches. They are preview assets, with local ad-hoc
signing rather than Apple notarization.

## Windows x64 installer and Herdr validation

- `python -m unittest discover -s tests -v` on Windows: **26 passed**,
  with nine macOS-only tests skipped. Windows PowerShell 5.1 runs the installer tests.
- Coverage includes Unicode/spaced paths, profile encodings and later user edits,
  PowerShell 7 syntax preserved by the PowerShell 5.1 installer, updates, rollback,
  uninstall, a running old executable, tampering, unsafe archives, shortcut collisions,
  redirected profiles and rollback after a profile write failure.
- Installer fixtures use a Windows-subsystem GUI executable for Herdr. This catches
  Windows PowerShell 5.1's asynchronous GUI execution behavior; version checks
  consume output through a pipeline before checking the exit code.
- GitHub Actions ran the source-tool, macOS-installer and Windows-installer jobs
  successfully for integration commit `51c2c82b9ba75cc0130ec69cdd7e25b3152b5ce2`.
- Fresh pinned Herdr source plus the public patch built with Rust 1.95.0,
  Zig 0.16.0 and libclang. `cargo +1.95.0 build --release --locked --jobs 1` passed.
- `cargo +1.95.0 test --locked --bin herdr-app --config
  'profile.dev.package."*".opt-level=0' --jobs 1 -- --test-threads=1`:
  **448 passed, two ignored**.
- The fresh GUI binary displayed an 800×400 PNG sent through a real local Windows
  core/ConPTY terminal. Only dedicated test windows were opened and closed; the
  original app and existing local/remote terminals remained live. No pointer input
  or paid model request was used. Screenshots with private workspace details were
  kept out of the public repository.
- The official Codex `rust-v0.169.1` Windows x64 platform archive was downloaded
  independently of the machine's existing Codex installation. Its GitHub asset
  digest was verified:
  `6fafb4a62e9d784eaeebabd3b1aa2539d48af753693f62800d73884fbf85600e`.
  A packaging regression confirms mismatched companion versions are rejected
  before any output archive is created.

### Existing Windows database compatibility

The official Windows Codex distribution embeds CRLF migration checksums. A native
build with LF migration source bytes can pass version/help checks yet reject an
existing database. The local integration check caught this before publication;
the incompatible private preview was quarantined and its GitHub draft was not
published. Existing user databases and original Codex executables were retained.

`tools/prepare_windows_codex.py` verifies the tracked SQL against the pinned Git
source and prepares the 78 state migration source files as CRLF for Windows builds.
It never reads or edits a user database. Source-preparation tests cover idempotency,
dry runs and rejection of semantic SQL edits before any writes.

`tools/check_codex_state.py` seeds an isolated temporary database with a canonical
Windows migration, starts an app-server without a model request, then verifies all
62 resulting state migration checksums. The official Windows 0.169.1 runtime
passed this check; the incompatible LF build was rejected. Packaging now requires
this check in addition to version/help and companion checks. Checker tests also
reject a zero-exit runtime that produces incorrect migration checksums.

The source fixture and checksum references are attributed in
[tests/fixtures](../tests/fixtures/README.md). macOS builds retain their original
source format; this preparation step applies only to Windows.

### Windows preview v0.1.0-preview.3

The corrected Windows x64 build passed with Rust 1.95.0 / MSVC, release
`opt-level=1`, `lto=false`, `codegen-units=16`, debug information disabled and
`strip=debuginfo`, using two build jobs. Source SQL was prepared with:

```powershell
python tools/prepare_windows_codex.py ../codex --apply
```

The native build used `cargo +1.95.0 --config windows-v8-source.toml build --locked
--release -p codex-cli --bin codex --jobs 2`. The local Cargo source replacement
used the exact pinned rusty_v8 archive to avoid Windows checkout path limits in
unused Chromium submodules: commit `90a65f887a0c0f048f3784afbcb320b373c8a2e0`, archive
SHA-256 `32bc3dac906adf19f98ea73f5882bccbdf68cd5e194135fb1b68b14f86178721`.
No external Cargo.lock package version changed. These are maintainer build details;
installers do not fetch source or invoke Cargo.

The 228,337,476-byte ZIP derives from integration commit
`e124073d03daeb0bc1358dd46ef8599fcd27ceb4`. SHA-256:
`c20f0588faa1154f2a3610b59a487b8c1009262f46cbe5ef31cb2f658f2aff54`.
The patched Codex executable is 364,297,728 bytes, SHA-256
`48b9c61cc8ddc407fd4677975e56cd803f854d12f04d291c8f1857dbd4c93182`.
Version/help/resume-help, companion search, file hashes and all 62 existing-database
fixture checksums passed. The installed runtime also read the existing user's
account limits successfully, without a model request or database reset.

Full ZIP installation, doctor, same-version reinstall and uninstall passed in
separate isolated homes under both Windows PowerShell editions. Project and
original configuration hashes stayed unchanged; profile bytes were restored exactly.

| Shell | Offline first install | Offline reinstall |
| --- | --- | --- |
| Windows PowerShell 5.1 | 31.36 s | 41.56 s |
| PowerShell 7 | 34.77 s | 41.44 s |

These local measurements exclude download and were taken while native tests were
compiling. They are not timing guarantees.

The real-user side-by-side upgrade from the unpublished test build took 39.11 s
offline. All pre-existing core terminals stayed live; original app, configuration,
authentication, global Codex and shortcut hashes remained unchanged. Existing
profile content was retained. The app reported no errors. A new real Herdr
PowerShell terminal selected the bundled 0.169.1 Codex and visibly rendered an
800×400 PNG fixture. Its existing custom usage sidebar also worked. No pointer
input or paid model request was used; private screenshots were not published.

The subsequent source patch normalizes both sides of a test-only Windows path
comparison (verbatim `\\?\` prefixes); it does not change production code.
The published ZIP retains the exact build and hashes recorded above.
Native terminal color tests require `NO_COLOR` to be unset and a color-capable
`TERM`; otherwise four cursor-color expectations fail under the build runner's
`NO_COLOR=1` environment. With that environment corrected, all 19 custom-terminal
tests passed, including image persistence across redraws and overlay removal.

After publishing v0.1.0-preview.3, the documented public `irm ... | iex` command
passed on the real Windows account. An uncached public download followed by a
same-version reinstall and app-open request took 89.72 s. This is not a cold
first-install timing. All 10 previously live terminals remained live. Original
app, settings, authentication, global Codex and shortcut hashes were unchanged;
existing profile content was retained, `doctor` passed, and app status had no errors.
GitHub validation run [44418741697](https://github.com/yanzzzzzzzzz/herdr-codex-images/actions/runs/44418741697)
passed all three jobs (packaging, macOS installer and Windows installer).
The final local `python -m unittest discover -s tests -v` run passed 26 tests with
9 macOS-only skips; `python tools/patch_component.py --validate` and
`git diff --check` also passed.

The corrected native Windows TUI tests also passed. With the same release flags,
`NO_COLOR` unset and `TERM=xterm-256color`, the command was:

```powershell
cargo +1.95.0 --config windows-v8-source.toml --config 'profile.release.package."codex-tui".opt-level=0' test --locked --release -p codex-tui --lib --jobs 2 FILTER -- --test-threads=1
```

Filters: `assistant_images` (1 passed, overlapping the next group),
`history_cell::messages` (16 passed), `transcript_view::` (274 passed),
`custom_terminal::` (19 passed), and
`transcript_image::composer::tests::original_` (1 passed): **310 distinct tests**.
This is targeted native validation, not the full 6,046-test upstream TUI suite.
The original user Herdr process remained running throughout validation.
