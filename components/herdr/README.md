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

The remote-original reader currently targets Unix hosts with `/usr/bin/perl`,
`JSON::PP`, `Fcntl`, and `Time::HiRes`. It uses existing core connections, bounded
chunks, and file-identity checks. A failed load keeps the transmitted preview.
Local Windows originals are supported; Windows remote-host originals are not validated.

The patch changes native Rust. It is not a drop-in JavaScript Herdr mod.
