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
