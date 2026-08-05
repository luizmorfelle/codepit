#!/usr/bin/env bash
# Installs Zellij, generates the codepit layout and creates the `cpit` alias.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZELLIJ_VERSION="v0.44.3"
BIN_DIR="$HOME/.local/bin"
LAYOUT_DIR="$HOME/.config/zellij/layouts"

mkdir -p "$BIN_DIR" "$LAYOUT_DIR"

# 1) Install Zellij (single binary, no root) into our own dir if it is not there yet.
#    We only check BIN_DIR (not the PATH): that pins the version, and since
#    ~/.local/bin comes first in the PATH, our copy is the one that runs.
if [ ! -x "$BIN_DIR/zellij" ]; then
  arch="$(uname -m)"
  echo "Downloading Zellij $ZELLIJ_VERSION ($arch)..."
  url="https://github.com/zellij-org/zellij/releases/download/${ZELLIJ_VERSION}/zellij-${arch}-unknown-linux-musl.tar.gz"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL "$url" -o "$tmp/zellij.tar.gz"
  tar -xzf "$tmp/zellij.tar.gz" -C "$tmp"
  install -m 0755 "$tmp/zellij" "$BIN_DIR/zellij"
  echo "Zellij installed at $BIN_DIR/zellij"
else
  echo "Zellij already present in $BIN_DIR."
fi

# 2) Generate the layout with this checkout's absolute paths (works from any folder).
#    (rm first: it may be a symlink from an older install → never write through it.)
rm -f "$LAYOUT_DIR/codepit.kdl"
python3 -c "import sys; sys.path.insert(0, '$ROOT'); from lib import config; open('$LAYOUT_DIR/codepit.kdl', 'w').write(config.build_layout(config.load(), '$ROOT'))"
echo "Layout generated at $LAYOUT_DIR/codepit.kdl"

# 2b) Link our config (pane keybinds) only if you do not have one of your own
ZCONFIG="$HOME/.config/zellij/config.kdl"
if [ ! -e "$ZCONFIG" ]; then
  ln -sf "$ROOT/config.kdl" "$ZCONFIG"
  echo "Zellij config linked at $ZCONFIG (Alt+t new pane, Alt+w close)"
else
  echo "$ZCONFIG already exists — add the Alt+t (NewPane) and Alt+w (CloseFocus) binds by hand if you want them."
fi

# 3) Create .env from the example (if it does not exist yet)
if [ ! -f "$ROOT/.env" ]; then
  [ -f "$ROOT/.env.example" ] || { echo "ERROR: .env.example not found in $ROOT"; exit 1; }
  cp "$ROOT/.env.example" "$ROOT/.env"
  chmod 600 "$ROOT/.env"
  echo "Created .env."
fi

# 4) PATH + alias in ~/.bashrc (idempotent)
add_line() { grep -qxF "$1" "$HOME/.bashrc" || echo "$1" >> "$HOME/.bashrc"; }
add_line 'export PATH="$HOME/.local/bin:$PATH"'
add_line "alias cpit='zellij --layout codepit'"

echo "Done. Now run 'python3 setup.py' to pick panels and data sources"
echo "(without it, the default is GitHub for both tickets and PRs)."
echo "Then: 'source ~/.bashrc' (or open a new shell) and 'cpit'."
