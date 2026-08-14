import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { churnFixture } from '../fixtures'
import type {
  BranchInfo,
  EnvState,
  FlowCell,
  FlowSettings,
  JournalEntry,
  PairedAgent,
  WorkbenchSession,
} from '../model/types'

/**
 * Derives the workbench's `?state=` variant by spread-transforming the churn
 * fixture — the fixtures module is never mutated. Each variant is the same flow
 * a moment later or a moment earlier: idle is the running fixture after the
 * train finishes, unpaired is idle after the agent session ends, empty is the
 * flow before anything exists.
 *
 * This is the **fixture** arm of the source switch in `live/source.ts`; the
 * live arm is `live/useFlowSession.ts` against a real daemon. Which one a page
 * takes is `selectSource`'s answer, and a `?state=` in the URL is one of the
 * things that decides it — so these variants stay reachable by link.
 */

export const WORKBENCH_VARIANTS = [
  'running',
  'idle',
  'unpaired',
  'empty',
  'kernel-not-started',
  'not-running',
  'locked',
] as const

export type WorkbenchVariant = (typeof WORKBENCH_VARIANTS)[number]

export interface WorkbenchState {
  variant: WorkbenchVariant
  session: WorkbenchSession
  env: EnvState
  settings: FlowSettings
  branches: BranchInfo[]
  cellsByBranch: Record<string, FlowCell[]>
  journal: JournalEntry[]
}

function variantOf(raw: unknown): WorkbenchVariant {
  return typeof raw === 'string' && (WORKBENCH_VARIANTS as readonly string[]).includes(raw)
    ? (raw as WorkbenchVariant)
    : 'running'
}

/** The running fixture a few minutes later: the train landed, downstream is stale on it. */
function settledMainCells(cells: FlowCell[]): FlowCell[] {
  return cells.map((cell): FlowCell => {
    if (cell.slug === 'train_model') {
      return {
        ...cell,
        status: 'materialized',
        stale: undefined,
        console: undefined,
        timing: { costSeconds: 312, finishedAgo: '24m ago' },
        logs: 'trained 24 epochs · best val_auc 0.841\ncheckpoint epoch_24.ubj staged\n',
      }
    }
    if (cell.slug === 'holdout_eval') {
      return {
        ...cell,
        stale: { kind: 'parent-rematerialized', cause: 'parent `train_model` rematerialized' },
      }
    }
    if (cell.stale?.transitive) {
      return {
        ...cell,
        stale: { ...cell.stale, cause: 'parent `train_model` rematerialized' },
      }
    }
    return cell
  })
}

/** The head journal entry once the running transaction has finished. */
function settledJournal(journal: JournalEntry[]): JournalEntry[] {
  const [head, ...rest] = journal
  if (!head || head.kind !== 'run') return journal
  return [{ ...head, summary: 'ran `train_model` · val_auc 0.841' }, ...rest]
}

function withMain(cellsByBranch: Record<string, FlowCell[]>, main: FlowCell[]) {
  return { ...cellsByBranch, main }
}

export function useWorkbenchState(route: RouteLocationNormalizedLoaded): WorkbenchState {
  const variant = variantOf(route.query.state)
  const fx = churnFixture

  const idlePaired: PairedAgent | undefined = fx.session.paired
    ? { ...fx.session.paired, state: 'idle', idleFor: '24m', task: undefined }
    : undefined

  switch (variant) {
    case 'idle':
      return {
        variant,
        session: { ...fx.session, state: 'idle', paired: idlePaired, changesBehind: 12 },
        env: fx.env,
        settings: fx.settings,
        branches: fx.branches,
        cellsByBranch: withMain(fx.cellsByBranch, settledMainCells(fx.cellsByBranch.main)),
        journal: settledJournal(fx.journal),
      }
    case 'unpaired':
      return {
        variant,
        session: { ...fx.session, state: 'unpaired', paired: undefined, worktreeLocked: false },
        env: fx.env,
        settings: fx.settings,
        branches: fx.branches.map((branch) =>
          branch.name === 'main' ? { ...branch, agent: undefined } : branch,
        ),
        cellsByBranch: withMain(fx.cellsByBranch, settledMainCells(fx.cellsByBranch.main)),
        journal: [
          {
            step: 24,
            time: '14:40',
            branch: 'main',
            actor: { kind: 'agent', label: 'claude-1' },
            intent: 'session end',
            kind: 'agent-end',
            summary: 'claude-1 session ended cleanly',
          },
          ...settledJournal(fx.journal),
        ],
      }
    case 'empty': {
      const emptyMain: BranchInfo = {
        name: 'main',
        parent: null,
        forkedAtStep: null,
        headStep: 0,
        lastIntent: 'flow initialized',
        settled: true,
        checkedOut: true,
      }
      return {
        variant,
        session: {
          ...fx.session,
          state: 'unpaired',
          paired: undefined,
          worktreeLocked: false,
          diskUsage: '12 KB',
        },
        env: fx.env,
        settings: fx.settings,
        branches: [emptyMain],
        cellsByBranch: { main: [] },
        journal: [],
      }
    }
    case 'kernel-not-started':
      return {
        variant,
        session: {
          ...fx.session,
          state: 'kernel-not-started',
          paired: idlePaired ? { ...idlePaired, idleFor: '2h' } : undefined,
        },
        env: fx.env,
        settings: fx.settings,
        branches: fx.branches,
        cellsByBranch: withMain(fx.cellsByBranch, settledMainCells(fx.cellsByBranch.main)),
        journal: settledJournal(fx.journal),
      }
    case 'not-running':
      // Everything else stays as last-known state — the banner marks it stale.
      return {
        variant,
        session: { ...fx.session, state: 'daemon-down' },
        env: fx.env,
        settings: fx.settings,
        branches: fx.branches,
        cellsByBranch: withMain(fx.cellsByBranch, settledMainCells(fx.cellsByBranch.main)),
        journal: settledJournal(fx.journal),
      }
    case 'running':
    case 'locked':
      return {
        variant,
        session: fx.session,
        env: fx.env,
        settings: fx.settings,
        branches: fx.branches,
        cellsByBranch: fx.cellsByBranch,
        journal: fx.journal,
      }
  }
}
