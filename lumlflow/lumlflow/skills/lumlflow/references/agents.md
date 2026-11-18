# Connecting a coding agent to Flow

An agent works in flows through Flow's MCP server, `lumlflow mcp` on stdio. It
needs no workspace argument: the agent passes the flow's path in each call.

## Set up the MCP entry

```bash
lumlflow agents list                  # detected agents and whether their entry is current
lumlflow agents setup claude-code     # write or update the user-level MCP entry
lumlflow agents remove claude-code
```

Agent ids: `claude-code`, `claude-desktop`, `cursor`, `windsurf`, `vscode`,
`codex`, `gemini`, `opencode`, `copilot`, `jetbrains-ai`. Some are detect-only:
`setup` refuses them and names the config file where the user pastes the entry
by hand. The Agents panel in `lumlflow ui` does the same. After setup, follow
the hint it prints, such as restarting the agent or approving the server.

## Without MCP

An agent that is itself a command-line program uses the same operations as
verbs: `lumlflow context`, `lumlflow cells new`, `lumlflow run` and the rest
listed in [flows.md](flows.md). To have its changes attributed to it, start it
through Flow:

```bash
lumlflow agent exec --label "my-agent" -- my-agent-command
```

## Working next to other agents

Several agents can work in one flow. The cell an agent last named is held for
it until it names another, disconnects or leaves it for three minutes. A
change to a cell someone else holds is refused and names who holds it; work on
another cell meanwhile. See the end of [flows.md](flows.md).
