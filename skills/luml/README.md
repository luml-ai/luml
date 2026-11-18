# LUML skill for coding agents

This skill tells a coding agent how to work with [LUML](https://luml.ai): which
LUML package fits the task, and how to load that package's own skill. The
package skills ship inside the packages, so they always match the installed
version.

It works with any agent that supports [Agent Skills](https://agentskills.io).

## Install

**Claude Code**

```text
/plugin install luml --marketplace luml-ai/luml
```

The skill then runs as `/luml:luml`, and Claude Code also loads it when the
task calls for it.

**Codex**

In Codex, ask the built-in installer:

```text
$skill-installer install https://github.com/luml-ai/luml/tree/main/skills/luml
```

**Cursor, Gemini CLI, OpenCode, Copilot and other agents**

```bash
npx skills add luml-ai/luml
```

The command asks which agents to install the skill for.

**By hand**

Copy this folder into the skills folder of your agent, for example
`~/.agents/skills/luml/` or `.agents/skills/luml/` in a project.

## Package skills

Each LUML package prints its own skill:

```bash
python -m luml skills show luml-sdk        # luml_sdk
python -m luml_api skills show luml-api    # luml_api
lumlflow skills show lumlflow              # lumlflow
python -m luml_mlflow skills show luml-mlflow   # luml-mlflow
```
