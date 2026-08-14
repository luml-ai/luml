/**
 * The prompt that pairs an agent with a flow, built locally, over the sample
 * flow `churn` on lane `main` in the workspace `/Users/you/work`.
 *
 * The daemon owns the real one — it knows where the workspace is, which
 * lane the files hold, and which `lumlflow` a config can actually spawn,
 * none of which a browser can work out — and `agent.connect` is where a live
 * surface asks for it. This is the shape that answer follows, and what the
 * fixtures and the gallery render, the same way `buildHandoffPayload` stands
 * behind a handoff.
 *
 * It is a copy of `daemon/connect.py`'s wording, hard-wrapped at the same 72
 * columns, so the specimen and the shipped prompt read alike. When that file
 * moves, this one moves with it.
 *
 * Assembled line by line rather than as one template because it carries fenced
 * code of its own, and a fence inside a template literal is a quoting puzzle
 * where the point is that the text reads exactly as it will be pasted.
 */
export const CONNECT_PROMPT = [
  `You are paired with the lumlflow flow \`churn\` in \`/Users/you/work\`, on`,
  `lane \`main\`. Its cells live there. So does every version of them, and`,
  'every result they produced. Connect to the flow and work through the',
  'connection. lumlflow then records what you do as yours.',
  '',
  'Register lumlflow as an MCP server:',
  '',
  '```json',
  '{',
  '  "mcpServers": {',
  '    "lumlflow": {',
  '      "command": "/Users/you/work/.venv/bin/lumlflow",',
  '      "args": ["mcp", "--workspace", "/Users/you/work"]',
  '    }',
  '  }',
  '}',
  '```',
  '',
  'A harness that configures MCP servers through its own UI or command',
  'takes the same two facts: the command above, and those arguments. Your',
  'harness sends its own name in the handshake. That name becomes the label',
  `this flow attributes your work to. Add \`--label <name>\` to the arguments`,
  'to be called something else.',
  '',
  'Then, before anything else:',
  '',
  `- Call \`context\`. It names the lane you are on, what is stale and`,
  '  why, and what failed.',
  `- Read \`/Users/you/work/AGENTS.md\`. It holds the cell DSL and the verbs.`,
  `- Read \`/Users/you/work/churn.flow/.lumlflow/CHECKOUT.md\`. It says what`,
  '  the files hold.',
  '',
  'While you are here:',
  '',
  `- Cells are files under \`churn.flow/cells/\`, one class each. Editing the`,
  `  file edits the cell. The \`edit-cell\` and \`new-cell\` tools do the same`,
  '  thing where you have no file tools.',
  `- Run a cell through the \`run\` tool. Never execute a cell file. Nothing`,
  '  in a cell runs at edit time. A run is what records a result.',
  `- Cells are non-interactive. \`input()\` fails immediately. Pass values`,
  `  through \`params\`, and secrets through \`ctx.secret("NAME")\`.`,
  `- Every change takes an \`intent\`. Write one line saying why. This flow's`,
  '  history reads it back.',
].join('\n')
