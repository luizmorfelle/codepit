# codepit

Your dev day on one terminal panel — a glass cockpit for code. Built on
[Zellij](https://zellij.dev) with Python **standard library only**, `codepit` shows,
without leaving the terminal: a block-font clock, your assigned tickets, the pull
requests waiting on you, and your Claude Code usage — in one refreshable pane. Every
panel and data source is chosen at setup.

Built as a personal study project. The interesting parts: **zero pip dependencies**, a
`curses` interactive pane, a hand-written **MCP-over-HTTP client** (no SDK), pluggable
backends behind a tiny dispatcher, and a plain `unittest` suite.

<!-- Screenshot: run `cpit`, capture the terminal, save as screenshot.png at the repo
     root, and replace this comment with: ![codepit](screenshot.png) -->


## Panels (toggle any of them at setup)

- **clock** — big block-font clock, date, and the Brazilian national holiday of the day.
- **claude** — your 5h / 7d / per-model Claude usage bars, read from the local Claude Code credentials.
- **tickets** — your open tickets, filterable by status with clickable chips and scroll.
- **prs** — open PRs where you're author *or* reviewer, with review/CI status badges.

## Data sources (pick one per panel at setup)

| Panel   | Sources                                   | Status                          |
|---------|-------------------------------------------|---------------------------------|
| tickets | **GitHub Issues**, **Jira**, **MCP**, Trello | GitHub + Jira + MCP work; Trello planned |
| prs     | **GitHub**, GitLab, Bitbucket, MCP        | GitHub works; the rest planned  |

Adding a backend is one file under `lib/tickets/` or `lib/prs/` plus a line in that
package's dispatcher — the contract is small (`fetch(cfg)` returning normalized dicts).

## Requirements

- A Linux/macOS terminal, Python 3.8+
- [Zellij](https://zellij.dev) — installed for you by `install.sh`
- [`gh`](https://cli.github.com) authenticated (`gh auth login`) — for the GitHub backends

## Install

```bash
./install.sh
python3 setup.py     # choose panels + sources (writes config.json, .env, layout)
source ~/.bashrc
cpit                 # open the dashboard
```

Skip `setup.py` and you get the defaults: GitHub for both tickets and PRs, all panels on.

### Try it with demo data

No accounts, no config — see the dashboard with invented tickets/PRs/usage:

```bash
CODEPIT_CONFIG=config.demo.json python3 widgets/board.py   # just the board pane
CODEPIT_CONFIG=config.demo.json cpit                       # the full layout
```

## Configuration

`setup.py` is interactive and re-runnable — run it any time to reconfigure. It writes:

- **`config.json`** (gitignored, per-user) — which panels, which source per panel, and
  non-secret options (PR role, repo filters).
- **`.env`** (gitignored, chmod 600) — secrets, e.g. the MCP key. GitHub backends need no
  secret; they use the `gh` CLI's own auth.
- the Zellij layout, regenerated to match the panels you kept.

To edit by hand instead, copy `.env.example` to `.env` and write `config.json` yourself
(see the defaults in `lib/config.py`).

## Shortcuts

**Zellij:** switch pane `Ctrl+p` + arrows · new shell tab `Alt+t` · close tab `Alt+w` ·
click a stacked pane's title to toggle it · detach `Ctrl+o d` · quit `Ctrl+q`.
(The `Alt+t`/`Alt+w` binds come from `config.kdl`; if you already have a
`~/.config/zellij/config.kdl`, add its `keybinds { shared { ... } }` block manually.)

**Pane (when focused):** `←/→` move chip · `space` toggle status filter · `a` all · `n` none ·
`↑/↓` (or `j/k`) move the ticket cursor · `Enter` open the selected ticket in the browser ·
`1`/`2`/`3` toggle PR category · `R` refresh · `q` quit. You can also click the chips and the `R` button.

## Tests

```bash
python3 -m unittest discover -s tests -t . -v
```

No dependencies to install — everything is Python standard library.

## License

[MIT](LICENSE)
