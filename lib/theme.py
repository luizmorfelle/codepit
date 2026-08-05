"""Color palette (256-color, Tokyo Night flavored) — single source for clock and board."""

# name -> xterm-256 index
COLORS = {
    "blue": 111,
    "green": 150,
    "yellow": 179,
    "red": 210,
    "purple": 141,
    "cyan": 117,
    "orange": 215,
    "text": 189,
    "dim": 60,
    "bg": 235,
}

RESET = "\033[0m"


def fg(name):
    """ANSI foreground code (256-color) for the given name."""
    return f"\033[38;5;{COLORS[name]}m"


def bg(name):
    """ANSI background code (256-color) for the given name."""
    return f"\033[48;5;{COLORS[name]}m"


def badge(label, color):
    """Label on a colored background with padding, for raw ANSI output (clock)."""
    return f"{bg(color)}{fg('bg')} {label} {RESET}"
