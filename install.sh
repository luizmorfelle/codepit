#!/usr/bin/env bash
# codepit installer — one command, does everything:
# installs Zellij, asks which panels/data sources you want, and launches the dashboard.
# Linux only (the Zellij binary and install paths below are Linux-specific).
set -euo pipefail

if [ "$(uname -s)" != "Linux" ]; then
  echo "codepit only supports Linux." >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ZELLIJ_VERSION="v0.44.3"
BIN_DIR="$HOME/.local/bin"
LAYOUT_DIR="$HOME/.config/zellij/layouts"
ZELLIJ="$BIN_DIR/zellij"

mkdir -p "$BIN_DIR" "$LAYOUT_DIR"

echo "== codepit setup =="
echo "This installs Zellij, asks which panels and data sources you want, writes your"
echo "config, and drops you straight into the dashboard. Re-run any time to reconfigure."
echo

# 1) Install Zellij (single binary, no root) into our own dir if not there yet.
#    We only check BIN_DIR (not the PATH): that pins the version, and since
#    ~/.local/bin comes first in the PATH, our copy is the one that runs.
if [ ! -x "$ZELLIJ" ]; then
  arch="$(uname -m)"
  echo "-> Downloading Zellij $ZELLIJ_VERSION ($arch)..."
  url="https://github.com/zellij-org/zellij/releases/download/${ZELLIJ_VERSION}/zellij-${arch}-unknown-linux-musl.tar.gz"
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  curl -fsSL "$url" -o "$tmp/zellij.tar.gz"
  tar -xzf "$tmp/zellij.tar.gz" -C "$tmp"
  install -m 0755 "$tmp/zellij" "$ZELLIJ"
  echo "   done."
else
  echo "-> Zellij already installed, skipping."
fi

# 2) Create .env (secrets file) from the example, if it doesn't exist yet.
if [ ! -f "$ROOT/.env" ]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  chmod 600 "$ROOT/.env"
  echo "-> Created .env (secrets go here; setup.py fills it in for you next)."
fi

# 3) Zellij pane keybinds (Alt+t new pane, Alt+w close) — only if you don't have your own.
ZCONFIG="$HOME/.config/zellij/config.kdl"
if [ ! -e "$ZCONFIG" ]; then
  ln -sf "$ROOT/config.kdl" "$ZCONFIG"
  echo "-> Linked Zellij keybinds at $ZCONFIG (Alt+t new pane, Alt+w close)."
else
  echo "-> $ZCONFIG already exists — add config.kdl's keybinds block by hand if you want them."
fi

# 4) PATH + alias in ~/.bashrc, so future shells just need: cpit
add_line() { grep -qxF "$1" "$HOME/.bashrc" || echo "$1" >> "$HOME/.bashrc"; }
add_line 'export PATH="$HOME/.local/bin:$PATH"'
add_line "alias cpit='zellij --layout codepit'"
echo "-> Added 'cpit' alias to ~/.bashrc (new shells can just run: cpit)."

# 5) Panels + data sources: interactive, writes config.json/.env/layout.
echo
echo "-- Now let's pick your panels and data sources --"
python3 "$ROOT/setup.py"

echo
echo "== all set =="
echo "Launching codepit now (Ctrl+p to switch panes, Ctrl+q to quit)."
echo "Next time, open a new terminal and just run: cpit"
sleep 1
exec "$ZELLIJ" --layout codepit
