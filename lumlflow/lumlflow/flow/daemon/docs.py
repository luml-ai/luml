from importlib.resources import files

# The agent guide is the Flow skill's `references/flows.md`, so `lumlflow guide`,
# the `lumlflow://guide` MCP resource and the skill serve one text.
CHEATSHEET = (
    files("lumlflow") / "skills" / "lumlflow" / "references" / "flows.md"
).read_text(encoding="utf-8")
