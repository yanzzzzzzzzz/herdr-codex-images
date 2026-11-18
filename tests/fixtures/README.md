`codex-state-0001.sql` is copied verbatim from OpenAI Codex commit
`c376cf7396eff83ce4c6ac61b9553df142e7a0be`, `codex-rs/state/migrations/0001_threads.sql`.
It is covered by the upstream Apache-2.0 license in `../../licenses/Codex-APACHE-2.0.txt`.

`codex-windows-state.json` records the SHA-384 checksums of the 62 migration sources
with CRLF line endings, matching the official Windows distribution. The runtime
check seeds migration 1 in an isolated temporary database, starts only an app-server
with empty input, then checks every resulting migration checksum. It never reads
or edits a user's Codex database, credentials, conversations or projects.
