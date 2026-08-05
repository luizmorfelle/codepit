"""Static command/shortcut cheatsheet content (terminal + dashboard).

Shortcuts verified against ~/.config/zellij/config.kdl (mode-based) +
the dashboard config.kdl (Alt t / Alt w)."""

ROWS = [
    ("Alt+←↑↓→", "focus pane"),
    ("Alt+t / w / f", "new shell / close / fullscreen"),
    ("Ctrl+t / Ctrl+q", "tab mode / quit zellij"),
    ("board", "R refresh · ←→ chip · space toggle · jk select · ↵ open · 1/2/3 PR · q"),
]


def one_line():
    """Single-line cheatsheet for the bottom bar: 'key desc  |  key desc  |  …'. Pure."""
    return "   |   ".join(f"{k} {d}" for k, d in ROWS)
