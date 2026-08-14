/**
 * The chrome around the two views: the branch tree, the intent timeline, the
 * workspace env, the flow's settings and the line that says who is working.
 *
 * This is the live counterpart of `pages/useWorkbenchState.ts` — same shapes,
 * read off the daemon instead of a fixture — so the left panel and the top bar
 * cannot tell which arm they are mounted over. Nothing here decides anything:
 * `settled` is the daemon's badge, the branch states are its verdicts, and a
 * kernel behind the env is a fact it reports rather than one this file infers
 * from a version string.
 *
 * The two reads refresh on different signals, on purpose. The **tree** moves
 * with every transaction — a run changes a branch's states, a fork adds a lane
 * — so it re-reads whenever the journal does. The **env** moves only when an
 * env transaction lands or a kernel restarts, and refetching a package list
 * twenty times through an agent's edit burst would be twenty round trips for a
 * list that cannot have changed.
 */

import { computed, ref, shallowRef, watch } from 'vue'
import type { ComputedRef, Ref } from 'vue'

import type { EnvReport } from '@/flow/api/client'
import type {
  BranchRecord,
  FlowOp,
  FlowSettingsReport,
  KernelReport,
  Transaction,
} from '@/flow/api/types'
import { formatBytes, formatCount } from '../model/format'
import type {
  ActorRef,
  BranchInfo,
  EnvState,
  FlowSettings,
  JournalEntry,
  JournalKind,
  WorkbenchSession,
} from '../model/types'
import { pairedAgent } from './pairing'
import type { FlowSessionHandle } from './useFlowSession'

export interface WorkbenchRecords {
  branches: Ref<BranchInfo[]>
  env: Ref<EnvState>
  settings: ComputedRef<FlowSettings>
  /** Newest first — the timeline reads down from what just happened. */
  journal: ComputedRef<JournalEntry[]>
  overview: ComputedRef<WorkbenchSession>
  /** Re-read the env: after a restart, and after an install lands. */
  refreshEnv: () => Promise<void>
  /**
   * Take the settings the daemon wrote. They live in `flow.yaml` rather than in
   * the journal, so no transaction announces the change and nothing would
   * re-read the brief the panel is drawn from.
   */
  applySettings: (settings: FlowSettingsReport) => void
}

export function useWorkbench(session: FlowSessionHandle): WorkbenchRecords {
  const records = ref<BranchRecord[]>([])
  const report = shallowRef<EnvReport | null>(null)
  const written = shallowRef<FlowSettingsReport | null>(null)

  async function loadTree(): Promise<void> {
    try {
      const tree = await session.request('tree', { flow: session.brief.value?.path })
      records.value = tree.branches
    } catch {
      // A tree that would not load leaves the last one standing: the branch
      // identifier going blank would read as a flow with no branches.
    }
  }

  async function refreshEnv(): Promise<void> {
    try {
      report.value = await session.request('env.status', {})
    } catch {
      // Same: the packages panel keeps what it had rather than emptying.
    }
  }

  watch(session.revision, () => void loadTree(), { immediate: true })

  // The brief is replaced when the flow opens and whenever the daemon announces
  // the kernel moving — the two moments the drift can differ. Watching the ref
  // rather than the state it carries is deliberate: a restart is a stop and a
  // start, and comparing values would let a quick one cancel itself out.
  watch(session.brief, () => void refreshEnv(), { immediate: true })

  // Every transaction since the last look, not just the newest: a replay
  // delivers a burst and Vue wakes this watcher once for all of it.
  let read = 0
  watch(session.transactions, (lines) => {
    const fresh = lines.filter((line) => line.step > read)
    if (fresh.length === 0) return
    read = fresh[fresh.length - 1].step
    if (fresh.some((line) => line.ops.some((op) => op.op === 'env_changed'))) void refreshEnv()
  })

  const branches = computed(() => records.value.map(branchInfo))
  const names = computed(
    () => new Map(records.value.map((record) => [record.branch_id, record.branch])),
  )

  return {
    branches,
    env: computed(() =>
      envState(report.value, session.brief.value?.flow ?? '', session.brief.value?.kernel),
    ),
    settings: computed(() => flowSettings(written.value ?? session.brief.value?.settings)),
    journal: computed(() =>
      [...session.transactions.value]
        .reverse()
        .map((transaction) => journalEntry(transaction, names.value)),
    ),
    overview: computed(() => overview(session)),
    refreshEnv,
    applySettings: (settings) => {
      written.value = settings
    },
  }
}

// --- branches ---------------------------------------------------------------

function branchInfo(record: BranchRecord): BranchInfo {
  return {
    name: record.branch,
    parent: record.parent,
    // A root branch was forked from nothing; the graph draws it as a lane that
    // starts at the origin rather than one that split off something.
    forkedAtStep: record.parent === null ? null : record.forked_at_step,
    headStep: record.last_intent?.step ?? record.forked_at_step,
    lastIntent: record.last_intent?.intent ?? '',
    settled: record.last_intent?.settled ?? false,
    checkpointStep: record.checkpoint ?? undefined,
    agent: record.agent ? { kind: 'agent', label: record.agent } : undefined,
    archived: record.archived,
    checkedOut: record.checked_out,
  }
}

// --- the intent timeline ----------------------------------------------------

/** Which glyph a transaction reads under. The first match in this order wins. */
const KINDS: [FlowOp['op'], JournalKind][] = [
  // A marker is journaled alone, so its position here is about reading rather
  // than precedence: what a checkpoint transaction says is that somebody
  // stopped and named this point, which outranks anything else in the line.
  ['checkpointed', 'checkpoint'],
  ['run_recorded', 'run'],
  ['branch_created', 'fork'],
  ['adopted', 'adopt'],
  ['renamed', 'rename'],
  ['cell_removed', 'delete'],
  ['upload_recorded', 'promote'],
  ['upload_state_changed', 'promote'],
  ['env_changed', 'env'],
  ['agent_begin', 'agent-begin'],
  ['agent_end', 'agent-end'],
]

export function journalEntry(transaction: Transaction, names: Map<string, string>): JournalEntry {
  const ops = new Set(transaction.ops.map((op) => op.op))
  const matched = KINDS.find(([op]) => ops.has(op))
  return {
    step: transaction.step,
    time: clockTime(transaction.ts),
    // Branch-less by construction for the workspace-scoped ones — an env
    // change belongs to every branch under it, not to the one it landed on.
    branch: transaction.branch ? (names.get(transaction.branch) ?? '') : '',
    actor: actor(transaction.actor),
    intent: transaction.intent,
    kind: transaction.offline ? 'offline' : (matched?.[1] ?? 'edit'),
    summary: summarize(transaction),
    settled: transaction.settled,
  }
}

/**
 * One line under the intent: what the transaction actually did. Counted from
 * the ops it carries rather than parsed back out of the intent, which is the
 * author's sentence and not a record of anything.
 */
function summarize(transaction: Transaction): string {
  const said: string[] = []
  let accepted = 0
  let hits = 0
  for (const op of transaction.ops) {
    switch (op.op) {
      case 'cell_accepted':
        accepted += 1
        break
      case 'memo_hit':
        hits += 1
        break
      case 'run_recorded':
        if (op.state !== 'running') said.push(`run ${op.state}`)
        break
      case 'renamed':
        said.push(`\`${op.old_slug}\` → \`${op.new_slug}\``)
        break
      case 'branch_created':
        said.push(`branch \`${op.name}\``)
        break
      case 'workspace_code_changed':
        said.push(changedFiles(op.changed_paths))
        break
      case 'env_changed':
        said.push(op.summary)
        break
      case 'upload_recorded':
        said.push(`uploaded to ${op.ref.collection}`)
        break
      // Publishing states are journal lines because a queue nobody can see is a
      // spinner: an upload waiting out an offline window says so here.
      case 'upload_state_changed':
        said.push(
          op.state === 'failed' && op.attempts
            ? `upload failed · ${formatCount(op.attempts, 'attempt')}`
            : `upload ${op.state}`,
        )
        break
      default:
        break
    }
  }
  if (accepted > 0) said.unshift(`${formatCount(accepted, 'cell')} accepted`)
  if (hits > 0) said.push(`${formatCount(hits, 'result')} reused`)
  return said.join(' · ')
}

function changedFiles(paths: string[]): string {
  const named = paths.slice(0, 2).map((path) => `\`${path}\``)
  const rest = paths.length - named.length
  return `${named.join(', ')}${rest > 0 ? ` and ${formatCount(rest, 'other')}` : ''} changed`
}

/** `user` is the one reserved actor; every other label is an agent's own. */
function actor(label: string): ActorRef {
  return { kind: label === 'user' ? 'user' : 'agent', label }
}

/** Local wall clock, because that is the one the reader was sitting at. */
function clockTime(ts: string): string {
  const at = new Date(ts)
  if (Number.isNaN(at.getTime())) return ''
  return `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`
}

// --- env and settings -------------------------------------------------------

/** A distribution name as PyPI compares them — the daemon normalizes too. */
function normalized(name: string): string {
  return name.trim().toLowerCase().replace(/_/g, '-')
}

/**
 * The env as it stands, and where the running kernel sits to it.
 *
 * The drift is read from `env.status` rather than from the brief, because the
 * brief is a snapshot of the moment this tab opened and drift is exactly the
 * thing that moves afterwards: a package installed under a live kernel is what
 * raises it, and restarting is what clears it. Reading it from the brief left
 * the banner unable to do either — it could not appear for an install this
 * session made, and would not go away once the restart it asked for had
 * happened. What still comes from the brief is the one fact only the handshake
 * knows: which Python the kernel is actually running.
 */
function envState(report: EnvReport | null, flow: string, kernel: KernelReport | undefined) {
  const here = report?.flows?.find((entry) => entry.flow === flow)
  const drift = here?.behind ?? kernel?.behind ?? []
  const behind = new Set(drift.map(normalized))
  return {
    // The running kernel's own version. Absent until one has started, and left
    // absent rather than guessed from the interpreter the daemon would spawn.
    pythonVersion: kernel?.python ?? '',
    packages: (report?.packages ?? []).map((pkg) => ({
      name: pkg.name,
      version: pkg.version,
      pendingRestart: behind.has(normalized(pkg.name)) || undefined,
    })),
    mismatch: (here?.restart_required ?? kernel?.restart_required) || undefined,
  } satisfies EnvState
}

/**
 * The daemon calls restarting on an env change `auto`; the panel calls it
 * "restart automatically". One vocabulary each, translated here.
 */
function flowSettings(report: FlowSettingsReport | undefined): FlowSettings {
  return {
    reactivity: report?.reactivity ?? 'auto',
    autoThresholdSeconds: report?.eager_cost_threshold_s ?? 5,
    onEnvChange: report?.env_policy === 'auto' ? 'restart' : (report?.env_policy ?? 'ask'),
  }
}

/** The same translation the other way, for the write. */
export function settingsReport(settings: FlowSettings): FlowSettingsReport {
  return {
    reactivity: settings.reactivity,
    eager_cost_threshold_s: settings.autoThresholdSeconds,
    env_policy: settings.onEnvChange === 'restart' ? 'auto' : settings.onEnvChange,
  }
}

// --- the session line -------------------------------------------------------

function overview(session: FlowSessionHandle): WorkbenchSession {
  const brief = session.brief.value
  const holder = session.agent.value
  return {
    flowName: brief?.flow ?? '',
    state: session.state.value,
    paired: pairedAgent(session),
    worktreeBranch: brief?.branch ?? '',
    // Only a worktree-attached session holds the lock; an MCP one edits the
    // store and never the files, so it blocks no checkout.
    worktreeLocked: holder?.worktree === true || undefined,
    changesBehind: session.changesBehind.value,
    diskUsage: brief ? formatBytes(brief.disk_bytes) : undefined,
  }
}
