#!/usr/bin/env python3
"""Interactive setup: pick panels and data sources, write config.json + .env + layout.

Lazy prompts (stdlib only). Re-run any time to reconfigure. Wave 1 backends:
tickets = github | mcp; PRs = github. The others (jira/trello/gitlab/bitbucket)
land in later waves — the config/dispatch is already plugin-shaped for them."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from lib import config  # noqa: E402

ENV_PATH = os.path.join(ROOT, ".env")
LAYOUT_PATH = os.path.expanduser("~/.config/zellij/layouts/codepit.kdl")
TICKET_BACKENDS = ["github", "jira", "mcp"]   # implemented so far
PR_BACKENDS = ["github"]


def ask(prompt, default=""):
    hint = f" [{default}]" if default else ""
    got = input(f"{prompt}{hint}: ").strip()
    return got or default


def ask_choice(prompt, choices, default):
    while True:
        got = ask(f"{prompt} ({'/'.join(choices)})", default).lower()
        if got in choices:
            return got
        print(f"  pick one of: {', '.join(choices)}")


def ask_list(prompt):
    got = ask(prompt)
    return [x.strip() for x in got.split(",") if x.strip()]


def set_env(key, value):
    """Set `export key="value"` in .env, replacing any existing line for key."""
    line = f'export {key}="{value}"'
    lines = []
    if os.path.exists(ENV_PATH):
        with open(ENV_PATH) as f:
            lines = f.read().splitlines()
    prefix = f"export {key}="
    replaced = False
    for i, ln in enumerate(lines):
        if ln.strip().startswith(prefix):
            lines[i] = line
            replaced = True
            break
    if not replaced:
        lines.append(line)
    with open(ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(ENV_PATH, 0o600)


def write_layout(cfg):
    """Write the generated layout to the Zellij layouts dir (replacing any symlink)."""
    os.makedirs(os.path.dirname(LAYOUT_PATH), exist_ok=True)
    if os.path.islink(LAYOUT_PATH):
        os.unlink(LAYOUT_PATH)  # don't write through the install.sh symlink into the repo
    with open(LAYOUT_PATH, "w") as f:
        f.write(config.build_layout(cfg, ROOT))


def configure_tickets():
    src = ask_choice("Ticket source", TICKET_BACKENDS, "github")
    node = {"source": src}
    if src == "github":
        node["repos"] = ask_list("  Limit to repos (owner or owner/repo, comma-separated; empty=all)")
    elif src == "jira":
        site = ask("  Jira site (e.g. https://you.atlassian.net)")
        if site:
            node["site"] = site
        set_env("JIRA_EMAIL", ask("  Jira account e-mail"))
        set_env("JIRA_TOKEN", ask("  API token (id.atlassian.com → Security → API tokens)"))
        node["projects"] = ask_list("  Projects (keys, comma-separated; empty=all)")
    elif src == "mcp":
        set_env("MCP_URL", ask("  MCP server endpoint (https://host/path/to/mcp)"))
        set_env("MCP_KEY", ask("  MCP key"))
        set_env("MCP_ASSIGNEE_ID", ask("  Your user id on that server"))
        projects = ask("  Projects (comma-separated; empty=all)")
        if projects:
            set_env("MCP_PROJECTS", projects)
    return node


def configure_prs():
    src = ask_choice("PR host", PR_BACKENDS, "github")
    node = {"source": src}
    if src == "github":
        node["role"] = ask_choice("  Include PRs as", ["author", "reviewer", "both"], "both")
        node["repos"] = ask_list("  Limit to repos (owner or owner/repo, comma-separated; empty=all)")
    return node


def ask_panels():
    print("Available panels: clock, claude, tickets, prs, heatmap, omniroute")
    raw = ask("Which panels (comma-separated, or 'all')", "all")
    if raw.strip().lower() == "all":
        return list(config.PANELS)
    return [p.strip() for p in raw.split(",") if p.strip() in config.PANELS]


def main():
    print("── codepit setup ──")
    panels = ask_panels()
    cfg = {"panels": panels}
    if "tickets" in panels:
        cfg["tickets"] = configure_tickets()
    if "prs" in panels:
        cfg["prs"] = configure_prs()

    config.save(cfg)
    write_layout(cfg)
    print(f"\nDone. Wrote {config.CONFIG_PATH} and {LAYOUT_PATH}.")
    print("Run 'cpit' (or 'source ~/.bashrc' first, if you just installed).")


if __name__ == "__main__":
    try:
        main()
    except (EOFError, KeyboardInterrupt):
        print("\naborted — nothing was written.")
