"""Pluggable ticket source. Each backend exposes fetch(cfg) -> [{key,status,summary,project}]."""


def fetch_issues(cfg):
    """Open tickets assigned to me, from the configured source. Raises RuntimeError on failure."""
    source = (cfg or {}).get("source", "github")
    if source == "github":
        from lib.tickets import github
        return github.fetch(cfg)
    if source == "jira":
        from lib.tickets import jira
        return jira.fetch(cfg)
    if source == "mcp":
        from lib import mcp_tickets  # hand-rolled MCP client, no SDK
        return mcp_tickets.fetch_issues()
    raise RuntimeError(f"ticket source '{source}' is not implemented yet")
