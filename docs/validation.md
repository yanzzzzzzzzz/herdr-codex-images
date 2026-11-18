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
