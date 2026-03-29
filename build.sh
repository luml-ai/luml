#!/usr/bin/env bash
set -euo pipefail

SPEC_FILE="SPEC.md"
MAX_COMMIT_MSG_LEN=72
MAX_TOP_LEVEL_TASKS=20

# Configure git identity
GIT_USER_NAME="${GIT_USER_NAME:-codie-dfs}"
GIT_USER_EMAIL="${GIT_USER_EMAIL:-codie-dfs@users.noreply.github.com}"
git config --global user.name "$GIT_USER_NAME"
git config --global user.email "$GIT_USER_EMAIL"

echo "[codie-apply] Starting spec apply loop."
echo "[codie-apply] Working directory: $(pwd)"
echo "[codie-apply] Current branch: $(git rev-parse --abbrev-ref HEAD)"

if [ ! -f "$SPEC_FILE" ]; then
    echo "[codie-apply] Error: No SPEC.md found. Run /define first."
    exit 1
fi

echo "[codie-apply] Found SPEC.md, validating structure..."

# --- Validate SPEC.md structure ---

REQUIRED_SECTIONS=("# Proposals" "# Design" "# Scenarios" "# Tasks")
spec_content=$(cat "$SPEC_FILE")

prev_pos=-1
for section in "${REQUIRED_SECTIONS[@]}"; do
    pos=$(echo "$spec_content" | grep -n "^${section}$" | head -1 | cut -d: -f1)
    if [ -z "$pos" ]; then
        echo "[codie-apply] Error: missing section '${section}' in SPEC.md."
        exit 1
    fi
    if [ "$prev_pos" -ge "$pos" ]; then
        echo "[codie-apply] Error: section '${section}' is out of order in SPEC.md. Expected after line ${prev_pos}, found at line ${pos}."
        exit 1
    fi
    echo "[codie-apply]   Section '${section}' found at line ${pos}."
    prev_pos=$pos
done

for i in "${!REQUIRED_SECTIONS[@]}"; do
    section="${REQUIRED_SECTIONS[$i]}"
    if [ $i -lt $(( ${#REQUIRED_SECTIONS[@]} - 1 )) ]; then
        next_section="${REQUIRED_SECTIONS[$((i + 1))]}"
        body=$(echo "$spec_content" | sed -n "/^${section}$/,/^${next_section}$/{ /^${section}$/d; /^${next_section}$/d; p; }")
    else
        body=$(echo "$spec_content" | sed -n "/^${section}$/,\${ /^${section}$/d; p; }")
    fi
    trimmed=$(echo "$body" | sed '/^[[:space:]]*$/d')
    if [ -z "$trimmed" ]; then
        echo "[codie-apply] Error: section '${section}' is empty in SPEC.md."
        exit 1
    fi
done

# --- Validate task count ---

top_level_tasks=$(grep -c '^\- \[ \]' "$SPEC_FILE" || true)
already_done=$(grep -c '^\- \[x\]' "$SPEC_FILE" || true)

if [ "$top_level_tasks" -gt "$MAX_TOP_LEVEL_TASKS" ]; then
    echo "[codie-apply] Error: SPEC.md has ${top_level_tasks} top-level tasks (max ${MAX_TOP_LEVEL_TASKS}). Break the spec into smaller pieces."
    exit 1
fi

echo "[codie-apply] Validation passed: ${#REQUIRED_SECTIONS[@]} sections present, ${top_level_tasks} remaining tasks, ${already_done} already done."

# --- Resolve feature branch ---

FEATURE_BRANCH="${1:-}"
if [ -z "$FEATURE_BRANCH" ]; then
    AGENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    FEATURE_BRANCH="${AGENT_BRANCH#codie/}"
    echo "[codie-apply] No feature branch specified, inferred '${FEATURE_BRANCH}' from current branch '${AGENT_BRANCH}'."
else
    echo "[codie-apply] Target feature branch: ${FEATURE_BRANCH}"
fi

PROMPT=$(cat <<'PROMPT_EOF'
You are working in **spec apply mode**. Your job is to implement **exactly one top-level task** from `SPEC.md` and then stop.

## Rules

1. **SPEC.md is the plan** — do not use EnterPlanMode or create alternative plans.
2. **One task per invocation** — find the first unchecked top-level task, implement it (including all its subtasks), mark it done, then stop. Do NOT continue to the next top-level task.
3. **Subtasks within a task** — subtasks break down the internal steps of a task. They may be run in parallel using the Agent tool if they are independent of each other.
4. **Tick checkboxes as you go** — after completing each subtask, update SPEC.md: `- [ ]` → `- [x]`. After all subtasks are done, mark the top-level task as done too.
5. **Do not modify the Proposals, Design, or Scenarios sections** — only the Tasks section checkboxes should change.
6. **If a task is ambiguous**, refer to the Design and Scenarios sections for clarification.
7. **Each top-level task is a self-contained unit** — it includes implementation, tests, and any config needed.
8. **Do NOT run git commands** — no git commit, git push, git checkout, git switch, or git branch. The outer script handles all git operations.

## Workflow

1. Read `SPEC.md` from the repo root.
2. Find the first unchecked top-level task (`- [ ]` at root indentation in the Tasks section).
3. Read the relevant Design and Scenarios sections for context.
4. If the task has subtasks, check which are independent and can be parallelized.
5. Implement the code, tests, and any necessary configuration.
6. Follow all project conventions (CLAUDE.md, existing code style, etc.).
7. Run tests and quality checks as appropriate.
8. Mark subtasks done as you complete them, then mark the top-level task done.
9. Stop. Do not proceed to the next top-level task.

Subtasks within a task may be run in parallel if independent. When in doubt, run sequentially.
PROMPT_EOF
)

# --- Main loop: one task per iteration ---

task_number=0

while true; do
    remaining=$(grep -c '^\- \[ \]' "$SPEC_FILE" || true)

    if [ "$remaining" -eq 0 ]; then
        echo "[codie-apply] All tasks complete."
        if [ -f "$SPEC_FILE" ]; then
            echo "[codie-apply] Removing $SPEC_FILE..."
            git rm "$SPEC_FILE"
            git commit -m "remove $SPEC_FILE"
        fi
        exit 0
    fi

    task_number=$((task_number + 1))
    echo ""
    echo "[codie-apply] ========================================"
    echo "[codie-apply]  Task $task_number ($remaining remaining)"
    echo "[codie-apply] ========================================"
    echo "[codie-apply] Invoking claude..."

    set +o pipefail
    MAX_THINKING_TOKENS="${CLAUDE_THINKING_BUDGET:-0}" \
    claude -p "$PROMPT" --model "${CLAUDE_MODEL:-claude-opus-4-6}" --effort "${CLAUDE_EFFORT:-max}" --allowedTools "Read,Edit,Write,Glob,Grep,Bash,Agent" --output-format stream-json --verbose 2>&1 \
        | while IFS= read -r line; do
            type=$(echo "$line" | jq -r '.type // empty' 2>/dev/null) || continue
            case "$type" in
                assistant)
                    text=$(echo "$line" | jq -r '(.message.content[]? | select(.type == "text") | .text // empty)' 2>/dev/null)
                    if [ -n "$text" ]; then
                        first_sentence=$(echo "$text" | head -1 | cut -c1-120)
                        echo "[claude] $first_sentence"
                    fi
                    tool=$(echo "$line" | jq -r '(.message.content[]? | select(.type == "tool_use") | .name // empty)' 2>/dev/null)
                    if [ -n "$tool" ]; then
                        input_summary=$(echo "$line" | jq -r '(.message.content[]? | select(.type == "tool_use") | .input | if .file_path then .file_path elif .command then .command elif .pattern then .pattern else "" end)' 2>/dev/null)
                        echo "[claude] -> ${tool}: ${input_summary}"
                    fi
                    ;;
                result)
                    result_text=$(echo "$line" | jq -r '.result // empty' 2>/dev/null)
                    if [ -n "$result_text" ]; then
                        first_sentence=$(echo "$result_text" | head -1 | cut -c1-120)
                        echo "[claude] Result: $first_sentence"
                    fi
                    ;;
            esac
        done
    set -o pipefail

    remaining_after=$(grep -c '^\- \[ \]' "$SPEC_FILE" || true)

    if [ "$remaining_after" -ge "$remaining" ]; then
        echo "[codie-apply] Error: no progress made — task was not checked off. Stopping."
        exit 1
    fi

    task_name=$(grep '^\- \[x\]' "$SPEC_FILE" | tail -1 | sed 's/^- \[x\] //' | head -c "$MAX_COMMIT_MSG_LEN")
    echo "[codie-apply] Task $task_number complete: ${task_name}"
    echo "[codie-apply] Committing changes..."
    git add -A
    git commit -m "task $task_number: $task_name"
    echo "[codie-apply] Committed. Moving to next task."
done
