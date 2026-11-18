#!/bin/sh
# Download-only installation: no compiler, Git, Python, sudo, reset, or session kill.
set -eu
VERSION=v0.1.0-preview.1
REPO=yanzzzzzzzzz/herdr-codex-images
ARCHIVE=
SUMS=
OPEN=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --version) VERSION=${2:?Missing version}; shift 2 ;;
    --archive) ARCHIVE=${2:?Missing archive}; shift 2 ;;
    --checksums) SUMS=${2:?Missing checksums}; shift 2 ;;
    --no-open) OPEN=0; shift ;;
    -h|--help) echo 'Usage: sh install.sh [--version TAG] [--archive FILE --checksums FILE] [--no-open]'; exit 0 ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done
fail() { echo "herdr-images: $*" >&2; exit 1; }
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || fail 'This release supports macOS Apple Silicon only.'
case "$VERSION" in v[0-9]* ) ;; *) fail 'Invalid release tag.' ;; esac
case "$VERSION" in *[!a-zA-Z0-9.-]*) fail 'Invalid release tag.' ;; esac
ROOT="$HOME/.local/share/herdr-codex-images"
APP="$HOME/Applications/Herdr Images.app"
COMMAND="$HOME/.local/bin/herdr-images"
PROFILE="${ZDOTDIR:-$HOME}/.zshrc"
ASSET="herdr-codex-images-$VERSION-macos-arm64.tar.gz"
link_depth=0
while [ -L "$PROFILE" ]; do
  link_depth=$((link_depth + 1))
  [ "$link_depth" -lt 20 ] || fail 'Shell profile symbolic-link loop.'
  target=$(readlink "$PROFILE")
  case "$target" in /*) PROFILE="$target" ;; *) PROFILE="$(dirname "$PROFILE")/$target" ;; esac
done
for command in curl tar shasum codesign; do command -v "$command" >/dev/null || fail "Missing macOS command: $command"; done
for path in "$ROOT" "$ROOT/versions" "$ROOT/app-home" "$PROFILE"; do
  [ ! -L "$path" ] || fail "Refusing to replace symbolic link: $path"
done
[ ! -e "$APP" ] || { [ -L "$APP" ] && [ "$(readlink "$APP")" = "$ROOT/current/Herdr Images.app" ]; } || fail "An unmanaged app already exists: $APP"
[ ! -e "$COMMAND" ] || { [ -L "$COMMAND" ] && [ "$(readlink "$COMMAND")" = "$ROOT/current/bin/herdr-images" ]; } || fail "An unmanaged command already exists: $COMMAND"
[ ! -L "$APP" ] || [ "$(readlink "$APP")" = "$ROOT/current/Herdr Images.app" ] || fail 'Unmanaged app link.'
[ ! -L "$COMMAND" ] || [ "$(readlink "$COMMAND")" = "$ROOT/current/bin/herdr-images" ] || fail 'Unmanaged command link.'
if [ -e "$ROOT/current" ] && [ ! -L "$ROOT/current" ]; then fail 'Unmanaged current path.'; fi
mkdir -p "$ROOT/versions" "$ROOT/backups" "$HOME/Applications" "$HOME/.local/bin"
chmod 700 "$ROOT" "$ROOT/backups"
# A directory lock prevents two installers from racing. It contains no user data.
mkdir "$ROOT/.install-lock" 2>/dev/null || fail 'Another installation is running.'
STAGE=$(mktemp -d "$ROOT/.install.XXXXXX")
cleanup() { rm -rf "$STAGE"; rmdir "$ROOT/.install-lock" 2>/dev/null || :; }
trap cleanup EXIT HUP INT TERM
printf 'Installing %s (prebuilt macOS arm64)\n' "$VERSION"
if [ -z "$ARCHIVE" ]; then
  CACHE="$HOME/Library/Caches/herdr-codex-images/$VERSION"
  mkdir -p "$CACHE"
  URL="https://github.com/$REPO/releases/download/$VERSION"
  curl -fL --retry 2 --connect-timeout 15 "$URL/SHA256SUMS" -o "$STAGE/SHA256SUMS"
  SUMS="$STAGE/SHA256SUMS"
  ARCHIVE="$CACHE/$ASSET"
  # Cached downloads are still verified below. A repeated install needs no archive transfer.
  if [ ! -f "$ARCHIVE" ]; then
    curl -fL --retry 2 --connect-timeout 15 --continue-at - "$URL/$ASSET" -o "$ARCHIVE.part"
    mv "$ARCHIVE.part" "$ARCHIVE"
  fi
fi
[ -f "$ARCHIVE" ] && [ -f "$SUMS" ] || fail 'Archive and checksums are both required.'
EXPECTED=$(awk -v asset="$ASSET" '$2 == asset { print $1 }' "$SUMS")
[ "${#EXPECTED}" -eq 64 ] || fail 'Missing or ambiguous archive checksum.'
case "$EXPECTED" in *[!a-f0-9]*) fail 'Malformed archive checksum.' ;; esac
ACTUAL=$(shasum -a 256 "$ARCHIVE" | awk '{print $1}')
[ "$ACTUAL" = "$EXPECTED" ] || fail "Checksum mismatch. Remove the cached archive and retry: $ARCHIVE"
tar -tzf "$ARCHIVE" > "$STAGE/members"
awk '/^\// || /(^|\/)\.\.(\/|$)/ || $0 !~ /^payload\// { bad=1 } END { exit bad }' "$STAGE/members" || fail 'Unsafe archive paths.'
tar -tvzf "$ARCHIVE" | awk 'substr($0,1,1) != "-" && substr($0,1,1) != "d" { bad=1 } END { exit bad }' || fail 'Archive contains unsupported links or special files.'
tar -xzf "$ARCHIVE" -C "$STAGE"
PAYLOAD="$STAGE/payload"
[ "$(cat "$PAYLOAD/VERSION")" = "$VERSION" ] || fail 'Archive version mismatch.'
(cd "$PAYLOAD" && shasum -a 256 -c FILES.sha256 >/dev/null) || fail 'Payload verification failed.'
"$PAYLOAD/codex/bin/codex" --version
"$PAYLOAD/Herdr Images.app/Contents/MacOS/Herdr" --version
"$PAYLOAD/core/bin/hc" --version
/usr/bin/codesign --verify --deep --strict "$PAYLOAD/Herdr Images.app"

# Keep the original app and config untouched. Clone config only on first install.
if [ ! -d "$ROOT/app-home" ]; then
  mkdir "$STAGE/app-home"
  SOURCE="${HERDR_APP_HOME:-$HOME/.config/herdr-app}"
  if [ -d "$SOURCE" ]; then
    for name in settings.json keys.json shared.json view.json window.json seen.json installed.json layouts mods frame data themes; do
      if [ -e "$SOURCE/$name" ]; then cp -Rp "$SOURCE/$name" "$STAGE/app-home/$name"; fi
    done
    echo 'Copied existing settings and spaces; the original config is unchanged.'
  fi
  mv "$STAGE/app-home" "$ROOT/app-home"
fi

# Finder launches need explicit paths. Sign locally after configuring the isolated app.
PLIST="$PAYLOAD/Herdr Images.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c 'Delete :LSEnvironment' "$PLIST" >/dev/null 2>&1 || :
/usr/libexec/PlistBuddy -c 'Add :LSEnvironment dict' "$PLIST"
/usr/libexec/PlistBuddy -c "Add :LSEnvironment:HERDR_APP_HOME string $ROOT/app-home" "$PLIST"
/usr/libexec/PlistBuddy -c "Add :LSEnvironment:PATH string $ROOT/current/codex/bin:$HOME/.local/bin:/opt/homebrew/bin:$ROOT/current/core/bin:/usr/bin:/bin:/usr/sbin:/sbin" "$PLIST"
/usr/bin/codesign --force --sign - --entitlements "$PAYLOAD/macos-entitlements.plist" "$PAYLOAD/Herdr Images.app"
/usr/bin/codesign --verify --deep --strict "$PAYLOAD/Herdr Images.app"

# Preserve unrelated shell edits and back up the exact file before editing one managed block.
mkdir -p "$(dirname "$PROFILE")"
if [ -f "$PROFILE" ]; then cp -p "$PROFILE" "$ROOT/backups/zshrc-$(date +%Y%m%d-%H%M%S)-$$"; fi
awk '
  $0 == "# BEGIN herdr-codex-images-installer" { if (inside) exit 2; inside=1; next }
  $0 == "# END herdr-codex-images-installer" { if (!inside) exit 2; inside=0; next }
  !inside { print }
  END { if (inside) exit 2 }
' "$PROFILE" 2>/dev/null > "$STAGE/zshrc" || { [ ! -e "$PROFILE" ] || fail 'Malformed managed shell block; profile unchanged.'; }
cat >> "$STAGE/zshrc" <<'PROFILE'
# BEGIN herdr-codex-images-installer
if [[ -n "${HC_TERMINAL_ID:-}" && -x "$HOME/.local/share/herdr-codex-images/current/codex/bin/codex" ]]; then
  export PATH="$HOME/.local/share/herdr-codex-images/current/codex/bin:$PATH"
fi
# END herdr-codex-images-installer
PROFILE
/bin/zsh -n "$STAGE/zshrc"

DEST="$ROOT/versions/$VERSION"
if [ -e "$DEST" ]; then
  [ -f "$DEST/ARCHIVE.sha256" ] && [ "$(cat "$DEST/ARCHIVE.sha256")" = "$EXPECTED" ] || fail 'Installed version differs; refusing to overwrite it.'
  (cd "$DEST" && shasum -a 256 -c INSTALLED.sha256 >/dev/null) || fail 'Installed files were modified; refusing to reuse them.'
else
  echo "$EXPECTED" > "$PAYLOAD/ARCHIVE.sha256"
  (cd "$PAYLOAD" && find . -type f ! -name INSTALLED.sha256 -exec shasum -a 256 {} \; > "$STAGE/INSTALLED.sha256")
  mv "$STAGE/INSTALLED.sha256" "$PAYLOAD/INSTALLED.sha256"
  mv "$PAYLOAD" "$DEST"
fi
OLD=$(readlink "$ROOT/current" 2>/dev/null || :)
case "$OLD" in ''|versions/v*) ;; *) fail 'Unmanaged current link.' ;; esac
if [ -n "$OLD" ] && [ "$OLD" != "versions/$VERSION" ]; then
  ln -s "$OLD" "$STAGE/previous"
  mv -fh "$STAGE/previous" "$ROOT/previous"
fi
ln -s "versions/$VERSION" "$STAGE/current"
mv -fh "$STAGE/current" "$ROOT/current"
cat "$STAGE/zshrc" > "$PROFILE"
ln -sfn "$ROOT/current/Herdr Images.app" "$APP"
ln -sfn "$ROOT/current/bin/herdr-images" "$COMMAND"
echo 'Ready. Open ~/Applications/Herdr Images.app, or run:'
echo "  \"$COMMAND\" open"
echo 'Existing terminals stay running. Start a new Codex process to use image previews.'
if [ "$OPEN" -eq 1 ]; then /usr/bin/open "$APP"; fi
