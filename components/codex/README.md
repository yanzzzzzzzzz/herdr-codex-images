# Codex component

Completed assistant messages expose existing local raster artifacts to the graphics
transcript. Images appear below the reply. Graphics rows do not become copy/search text.
Draft thumbnail references also carry an explicit original-file URI when running in Herdr.

Pinned source: `openai/codex`, tag `rust-v0.169.1`, commit
`c376cf7396eff83ce4c6ac61b9553df142e7a0be`.

From the integration repository root:

```sh
git clone --branch rust-v0.169.1 --single-branch --filter=blob:none https://github.com/openai/codex.git ../codex
python tools/patch_component.py codex ../codex
python tools/patch_component.py codex ../codex --apply
cd ../codex/codex-rs
cargo +1.95.0 build --locked --release -p codex-cli --bin codex --jobs 2
```

Use the [upstream native build prerequisites](https://github.com/openai/codex/blob/rust-v0.169.1/docs/install.md).
Native release builds were validated on macOS ARM64 with Command Line Tools and
Windows x64 with MSVC. See the [validation record](../../docs/validation.md) for
the Windows pinned-source workaround. The patch also repairs
the tag's lockfile workspace versions from `0.0.0` to `0.169.1`: 173 workspace entries,
no external dependency upgrades.

## Deployment boundary

Building `codex-cli` alone does not create a complete distributable package. Preserve
the matching upstream platform bundle layout, including `bin/codex-code-mode-host`,
`codex-path`, `codex-resources`, `codex-package.json`, and applicable notices. Replace
only its `bin/codex` with the custom build. Keep the official installation available.
Prebuilt bundles and installers are available from the repository README. Manual
source deployment still needs the complete matching platform bundle above.

Start a new process after deploying:

```sh
codex --no-daemon
# Or choose an existing conversation:
codex --no-daemon resume
```

Graphics require a supported protocol and the rich owned transcript. Raw/text-only
surfaces retain links. Paths resolve against the reply's captured working directory;
files on another app-server machine are not implicitly copied.

## Relationship to upstream

Upstream already has image rendering for inspected/generated artifacts, discussed in
[issue #29451](https://github.com/openai/codex/issues/29451). This component extends
ordinary assistant Markdown links and code-formatted paths, multiple-image layout,
and the original-image reference used by the Herdr component.
