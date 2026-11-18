# Herdr component

Click a terminal bitmap to inspect it in a separate native window. Compatible image
references lazily load an original file from the terminal's machine. Shift-click
retains normal terminal selection/program mouse behavior.

Pinned source: `herdrdev/herdr-app`, tag `v0.1.16`, commit
`034f8b85f7e6bb71f8ff55cb4a80c548b2578c0f`.

From the integration repository root:

```sh
git clone --branch v0.1.16 --recurse-submodules https://github.com/herdrdev/herdr-app.git ../herdr-app
python tools/patch_component.py herdr ../herdr-app
python tools/patch_component.py herdr ../herdr-app --apply
```

Follow the [upstream build requirements](https://github.com/herdrdev/herdr-app/blob/v0.1.16/AGENTS.md).
The validated Windows build used Rust 1.95.0, Zig 0.16.0, and libclang 18.1.1.
Set `ZIG` and `LIBCLANG_PATH` for your own toolchain locations, then:

```sh
cd ../herdr-app
cargo +1.95.0 build --release --locked --jobs 2
```

This creates a build, not an installation. Back up your existing app before any manual
deployment. A source build does not enable Herdr's official automatic updates.
Do not stop herdr-core or other people's terminals to deploy a GUI build.

### macOS Apple Silicon

The same pinned patch was built and installed on a Mac mini with Rust 1.95.0,
Zig 0.16.0, and Apple's Command Line Tools. Configure `ZIG`, `SDKROOT`, and
`LIBCLANG_PATH` for those installations. Where full Xcode is not configured,
`DEVELOPER_DIR=/Library/Developer/CommandLineTools` selects the installed CLT
for this build without changing the global developer directory.

For tests on recent macOS, avoid the toolchain's stripped build-time dylib issue:

```sh
export CARGO_PROFILE_DEV_DEBUG=1 CARGO_PROFILE_TEST_DEBUG=1
cargo +1.95.0 test --locked --bin herdr-app \
  --config 'profile.dev.package."*".opt-level=0' \
  --config 'profile.dev.build-override.strip="none"' \
  --config 'profile.test.build-override.strip="none"' \
  --jobs 2 -- --test-threads=1
cargo +1.95.0 build --release --locked --jobs 2
```

Ensure `git` in the test environment works independently of any pending full-Xcode
license prompt. Manual app deployment must retain the upstream macOS entitlements,
including `com.apple.security.cs.allow-jit`, and verify the resulting app signature.
Locally signed builds are not notarized distributable releases.

The remote-original reader currently targets Unix hosts with `/usr/bin/perl`,
`JSON::PP`, `Fcntl`, and `Time::HiRes`. It uses existing core connections, bounded
chunks, and file-identity checks. A failed load keeps the transmitted preview.
Local Windows originals are supported; Windows remote-host originals are not validated.

The patch changes native Rust. It is not a drop-in JavaScript Herdr mod.
