"""User config for the dashboard: which panels to show and where data comes from.

Non-secret choices live in config.json (gitignored, per-user); secrets stay in .env.
If config.json is absent, DEFAULTS apply — a fresh clone shows GitHub issues + PRs."""
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config.json")

PANELS = ["clock", "claude", "tickets", "prs", "heatmap", "omniroute"]
TICKET_SOURCES = ["github", "jira", "trello", "mcp"]
PR_SOURCES = ["github", "gitlab", "bitbucket", "mcp"]

DEFAULTS = {
    "panels": list(PANELS),
    "tickets": {"source": "github", "repos": []},
    "prs": {"source": "github", "role": "both", "repos": []},
}


def load(path=None):
    """Config with DEFAULTS filled in for any missing top-level key. Never raises.
    Path precedence: explicit arg > $CODEPIT_CONFIG > config.json."""
    cfg = {k: (v.copy() if isinstance(v, dict) else list(v)) for k, v in DEFAULTS.items()}
    try:
        with open(path or os.environ.get("CODEPIT_CONFIG") or CONFIG_PATH) as f:
            user = json.load(f)
    except (OSError, ValueError):
        return cfg
    for k, v in user.items():
        cfg[k] = v
    return cfg


def save(cfg, path=None):
    with open(path or CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def panel_enabled(cfg, name):
    return name in cfg.get("panels", PANELS)


def board_enabled(cfg):
    """The board pane exists if any of its cards (claude/tickets/prs/heatmap/omniroute) is on."""
    return any(panel_enabled(cfg, p) for p in ("claude", "tickets", "prs", "heatmap", "omniroute"))


def _pane(name, cmd, size=None, borderless=True):
    size_attr = f" size={size}" if size else ""
    bl = " borderless=true" if borderless else ""
    return (f'pane name="{name}"{size_attr}{bl} command="bash" {{\n'
            f'    args "-lc" "{cmd}"\n'
            f'}}')


def build_layout(cfg, root):
    """Generate the Zellij layout (KDL) honoring which panels are enabled. Pure.

    Structure: a full-width content region on top and a single-line Shortcuts bar
    at the very bottom. The content is left column (clock + one shell) + the
    board."""
    src = f'source {root}/.env 2>/dev/null; exec '
    clock = _pane("Clock", f"{src}python3 {root}/widgets/clock.py", size='"20%"')
    shell = ('pane focus=true command="bash" {\n'
             '    args "-lc" "cd $HOME; claude; exec bash -i"\n'
             '}')
    shortcuts = _pane("Shortcuts", f"exec python3 {root}/widgets/cheatsheet.py", size="1")

    left_children = (
        ([clock] if panel_enabled(cfg, "clock") else [])
        + [shell]
    )
    left_body = "\n".join(left_children)
    if board_enabled(cfg):
        board = _pane("Board", f"{src}python3 {root}/widgets/board.py", size='"30%"')
        left = f'pane split_direction="horizontal" size="70%" {{\n{left_body}\n}}'
        content = f'pane split_direction="vertical" {{\n{left}\n{board}\n}}'
    else:
        content = f'pane split_direction="horizontal" {{\n{left_body}\n}}'

    return (f'layout {{\n    tab name="Dashboard" focus=true {{\n'
            f'        pane split_direction="horizontal" {{\n'
            f'{content}\n{shortcuts}\n'
            f'        }}\n    }}\n}}\n')
