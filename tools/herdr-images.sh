#!/bin/sh
set -eu
ROOT="$HOME/.local/share/herdr-codex-images"
APP="$HOME/Applications/Herdr Images.app"
PROFILE="${ZDOTDIR:-$HOME}/.zshrc"
link_depth=0
while [ -L "$PROFILE" ]; do
  link_depth=$((link_depth + 1))
  [ "$link_depth" -lt 20 ] || { echo 'Shell profile symbolic-link loop.' >&2; exit 1; }
  target=$(readlink "$PROFILE")
  case "$target" in /*) PROFILE="$target" ;; *) PROFILE="$(dirname "$PROFILE")/$target" ;; esac
done
case "${1:-help}" in
  open)
    exec /usr/bin/open "$APP"
    ;;
  doctor)
    [ -L "$ROOT/current" ] && [ -d "$ROOT/current" ] || { echo 'No active installation.' >&2; exit 1; }
    printf 'Release: '; cat "$ROOT/current/VERSION"
    (cd "$ROOT/current" && shasum -a 256 -c INSTALLED.sha256 >/dev/null)
    /usr/bin/codesign --verify --deep --strict "$APP"
    "$ROOT/current/Herdr Images.app/Contents/MacOS/Herdr" --version
    "$ROOT/current/codex/bin/codex" --version
    "$ROOT/current/codex/bin/codex" --help >/dev/null
    "$ROOT/current/codex/codex-path/rg" --version >/dev/null
    "$ROOT/current/core/bin/hc" --version
    [ -f "$ROOT/app-home/settings.json" ] || echo 'Settings will be created on first launch.'
    echo 'OK: isolated app, image-enabled Codex, core, and app signature.'
    ;;
  status|ls|shot)
    command=$1; shift
    export HERDR_APP_HOME="$ROOT/app-home"
    exec "$ROOT/current/Herdr Images.app/Contents/MacOS/Herdr" "$command" "$@"
    ;;
  update)
    echo 'The legacy native-preview updater is retired. Use an explicit verified standalone viewer release; no programs or settings were changed.' >&2
    exit 1
    ;;
  rollback)
    previous=$(readlink "$ROOT/previous" 2>/dev/null || :)
    current=$(readlink "$ROOT/current" 2>/dev/null || :)
    case "$previous" in versions/v*) ;; *) echo 'No previous release to restore.' >&2; exit 1 ;; esac
    case "$current" in versions/v*) ;; *) echo 'No managed active release.' >&2; exit 1 ;; esac
    [ -d "$ROOT/$previous" ] || { echo 'Previous release is missing.' >&2; exit 1; }
    mkdir "$ROOT/.install-lock" 2>/dev/null || { echo 'Another installation is running.' >&2; exit 1; }
    trap 'rmdir "$ROOT/.install-lock"' EXIT HUP INT TERM
    ln -s "$previous" "$ROOT/.rollback-current"
    ln -s "$current" "$ROOT/.rollback-previous"
    mv -fh "$ROOT/.rollback-current" "$ROOT/current"
    mv -fh "$ROOT/.rollback-previous" "$ROOT/previous"
    echo 'Restored previous release. Reopen Herdr Images when convenient; terminals are unchanged.'
    ;;
  uninstall)
    [ ! -L "$PROFILE" ] || { echo 'Refusing to edit a symbolic-link shell profile.' >&2; exit 1; }
    mkdir "$ROOT/.install-lock" 2>/dev/null || { echo 'Another installation is running.' >&2; exit 1; }
    trap 'rmdir "$ROOT/.install-lock"' EXIT HUP INT TERM
    if [ -f "$PROFILE" ]; then
      backup="$ROOT/backups/zshrc-uninstall-$(date +%Y%m%d-%H%M%S)-$$"
      cp -p "$PROFILE" "$backup"
      candidate="$ROOT/.uninstall-zshrc"
      awk '
        $0 == "# BEGIN herdr-codex-images-installer" { if (inside) exit 2; inside=1; next }
        $0 == "# END herdr-codex-images-installer" { if (!inside) exit 2; inside=0; next }
        !inside { print }
        END { if (inside) exit 2 }
      ' "$PROFILE" > "$candidate"
      /bin/zsh -n "$candidate"
      cat "$candidate" > "$PROFILE"
      rm "$candidate"
    fi
    for link in "$APP" "$HOME/.local/bin/herdr-images"; do
      if [ -L "$link" ]; then
        case "$(readlink "$link")" in "$ROOT/current/Herdr Images.app"|"$ROOT/current/bin/herdr-images") rm "$link" ;; esac
      fi
    done
    [ ! -L "$ROOT/current" ] || rm "$ROOT/current"
    echo 'Uninstalled app/command links and shell integration. Backups, settings and cached versions are retained.'
    echo 'No running terminal or original Herdr installation was stopped or removed.'
    ;;
  *) echo 'Usage: herdr-images {open|doctor|status|ls|shot|update|rollback|uninstall}' ;;
esac
