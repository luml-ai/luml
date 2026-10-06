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
  journal: ComputedRef<JournalEntry[]>
  overview: ComputedRef<WorkbenchSession>
  refreshEnv: () => Promise<void>
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
    }
  }

  async function refreshEnv(): Promise<void> {
    try {
      report.value = await session.request('env.status', {
        directory: session.brief.value?.workspace,
      })
    } catch {
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
    journal: computed(() => journalEntries(session.transactions.value, names.value)),
    overview: computed(() => overview(session)),
    refreshEnv,
    applySettings: (settings) => {
      written.value = settings
    },
  }
}

function branchInfo(record: BranchRecord): BranchInfo {
  return {
    name: record.branch,
    parent: record.parent,
    forkedAtStep: record.parent === null ? null : record.forked_at_step,
    parentStep: record.parent === null ? null : record.parent_step,
    headStep: record.head_step,
    newestStep: record.newest_step,
    lastIntent: record.last_intent?.intent ?? '',
    settled: record.last_intent?.settled ?? false,
    checkpointStep: record.checkpoint ?? undefined,
    agent: record.agent ? { kind: 'agent', label: record.agent } : undefined,
    archived: record.archived,
    checkedOut: record.checked_out,
  }
}

const KINDS: [FlowOp['op'], JournalKind][] = [
  ['rewound', 'rewind'],
  ['run_recorded', 'run'],
  ['worktree_bound', 'checkout'],
  ['branch_created', 'fork'],
  ['adopted', 'adopt'],
  ['renamed', 'rename'],
  ['cell_removed', 'delete'],
  ['cell_noted', 'note'],
  ['env_changed', 'env'],
  ['agent_begin', 'agent-begin'],
  ['agent_end', 'agent-end'],
]

export function journalEntries(
  transactions: readonly Transaction[],
  names: Map<string, string>,
): JournalEntry[] {
  const marks = new Map<number, string>()
  const entries: JournalEntry[] = []
  const stood = new Map<string, number>()
  for (const transaction of transactions) {
    const mark = markOf(transaction)
    if (mark !== null) {
      const at = mark.step ?? (transaction.branch ? stood.get(transaction.branch) : undefined)
      if (at !== undefined) marks.set(at, mark.words)
      continue
    }
    const entry = journalEntry(transaction, names)
    if (entry.position && transaction.branch) stood.set(transaction.branch, entry.step)
    entries.push(entry)
  }
  return entries
    .map((entry) => {
      const mark = marks.get(entry.step)
      return mark === undefined ? entry : { ...entry, mark }
    })
    .reverse()
}

function markOf(transaction: Transaction): { step: number | null; words: string } | null {
  if (transaction.ops.length === 0) return null
  if (!transaction.ops.every((op) => op.op === 'checkpointed')) return null
  const [op] = transaction.ops
  if (op.op !== 'checkpointed') return null
  return { step: op.step ?? null, words: transaction.intent }
}

export function journalEntry(transaction: Transaction, names: Map<string, string>): JournalEntry {
  const ops = new Set(transaction.ops.map((op) => op.op))
  const matched = KINDS.find(([op]) => ops.has(op))
  return {
    step: transaction.step,
    time: clockTime(transaction.ts),
    branch: transaction.branch ? (names.get(transaction.branch) ?? '') : '',
    actor: actor(transaction.actor),
    intent: transaction.intent,
    kind: transaction.offline ? 'offline' : (matched?.[1] ?? 'edit'),
    summary: summarize(transaction),
    settled: transaction.settled,
    position: isPosition(transaction),
  }
}

const NOT_A_PLACE = new Set<FlowOp['op']>([
  'worktree_bound',
  'cell_noted',
  'flag_set',
  'agent_begin',
  'agent_end',
  'workspace_code_changed',
  'env_changed',
  'branch_archived',
  'checkpointed',
  'rewound',
])

function isPosition(transaction: Transaction): boolean {
  if (transaction.actor === 'auto') return false
  if (transaction.ops.length === 0) return true
  return !transaction.ops.every((op) => NOT_A_PLACE.has(op.op))
}

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
      case 'rewound':
        said.push(`now at step ${op.to_step}`)
        break
      case 'workspace_code_changed':
        said.push(changedFiles(op.changed_paths))
        break
      case 'env_changed':
        said.push(op.summary)
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

function actor(label: string): ActorRef {
  return { kind: label === 'user' ? 'user' : 'agent', label }
}

function clockTime(ts: string): string {
  const at = new Date(ts)
  if (Number.isNaN(at.getTime())) return ''
  return `${String(at.getHours()).padStart(2, '0')}:${String(at.getMinutes()).padStart(2, '0')}`
}

function normalized(name: string): string {
  return name.trim().toLowerCase().replace(/_/g, '-')
}

function envState(report: EnvReport | null, flow: string, kernel: KernelReport | undefined) {
  const here = report?.flows?.find((entry) => entry.flow === flow)
  const drift = here?.behind ?? kernel?.behind ?? []
  const behind = new Set(drift.map(normalized))
  return {
    pythonVersion: kernel?.python ?? '',
    interpreter: report?.python,
    packages: (report?.packages ?? []).map((pkg) => ({
      name: pkg.name,
      version: pkg.version,
      pendingRestart: behind.has(normalized(pkg.name)) || undefined,
    })),
    mismatch: (here?.restart_required ?? kernel?.restart_required) || undefined,
  } satisfies EnvState
}

function flowSettings(report: FlowSettingsReport | undefined): FlowSettings {
  return {
    reactivity: report?.reactivity ?? 'auto',
    autoThresholdSeconds: report?.eager_cost_threshold_s ?? 5,
  }
}

export function settingsReport(settings: FlowSettings): FlowSettingsReport {
  return {
    reactivity: settings.reactivity,
    eager_cost_threshold_s: settings.autoThresholdSeconds,
  }
}

function overview(session: FlowSessionHandle): WorkbenchSession {
  const brief = session.brief.value
  return {
    flowName: brief?.flow ?? '',
    state: session.state.value,
    paired: pairedAgent(session),
    worktreeBranch: brief?.branch ?? '',
    changesBehind: session.changesBehind.value,
    diskUsage: brief ? formatBytes(brief.disk_bytes) : undefined,
  }
}
