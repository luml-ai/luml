/**
 * The browser's door to the workspace daemon — the same `Api` the socket
 * answers with, so the tab and the CLI cannot disagree about what a verb does.
 *
 * Two failure kinds, kept apart on purpose. A **refusal** is the runtime naming
 * something the caller did (no such cell, an edit against a moved head): it
 * crosses as itself and the surface renders the sentence. A **transport
 * failure** is nobody answering, which is the daemon-down state and not an
 * error about the request at all. Collapsing the two would leave the workbench
 * showing "no such cell" when what happened is that the daemon stopped.
 *
 * Every mutating verb takes an `intent`. It is the journal's mandatory field
 * and the string the transaction feed and the coalesced toasts read back, so
 * the type here is what stops an op from landing as an anonymous mutation.
 */

import type {
  AgentHarness,
  AssetPage,
  AssetView,
  BranchDiff,
  BranchRecord,
  CellContextPayload,
  CellDetail,
  CellLogs,
  CellSummary,
  EvalResult,
  FlagCode,
  FlowBrief,
  FlowExport,
  FlowSettingsReport,
  FlowStatus,
  JournalPage,
  KernelReport,
  Preflight,
  RunOutcome,
  StaleState,
  WorkspaceStatus,
} from './types'
import { rejectToken } from './token'

export const RPC_PATH = '/api/flow/rpc'
export const DOWNLOAD_PATH = '/api/flow/download'
export const TOKEN_HEADER = 'x-lumlflow-token'

/** The daemon's answer to a token it does not hold. */
const UNAUTHORIZED = 401

/** A refusal the daemon named. `kind` is the error class it named it with. */
export class FlowApiError extends Error {
  readonly kind: string | undefined
  readonly status: number

  constructor(message: string, options: { kind?: string; status: number }) {
    super(message)
    this.name = 'FlowApiError'
    this.kind = options.kind
    this.status = options.status
  }
}

/** Nobody answered. Not a verdict about the request — the not-running state. */
export class DaemonUnreachable extends Error {
  readonly reason: unknown

  constructor(method: string, reason?: unknown) {
    super(`lumlflow did not answer \`${method}\``)
    this.name = 'DaemonUnreachable'
    this.reason = reason
  }
}

interface Method<P, R> {
  params: P
  result: R
}

export interface FlowScoped {
  /** Omitted addresses a single-flow workspace; the daemon names candidates otherwise. */
  flow?: string
}

export interface BranchScoped extends FlowScoped {
  /** Omitted reads the branch the worktree is bound to. */
  branch?: string
}

/** Mutating verbs carry the journal's mandatory intent. */
export interface Intentful extends BranchScoped {
  intent: string
  actor?: string
}

export interface PingResult {
  workspace: string
  pid: number
  web: string | null
}

export interface CellsPage {
  flow: string
  branch: string
  cells: CellSummary[]
}

export interface WorkspaceFlow {
  name: string
  path: string
  relative_path: string
}

export interface WorkspaceListing {
  directory: string
  flows: WorkspaceFlow[]
}

export interface BranchTree {
  flow: string
  branch: string
  branches: BranchRecord[]
}

export interface ContextBrief {
  workspace: string
  python: { path: string; source: string }
  flow: string
  branch: string
  checked_out: boolean
  agent: string | null
  checkpoint: { step: number; intent: string; ts: string; mark: string | null } | null
  cells: number
  unsynced: { slug: string; state: StaleState; causes: string[] }[]
  unsynced_omitted: number
  failures: { slug: string; error: string | null }[]
  pending: { recompute: string[]; estimate_seconds: number }
  recent: { step: number; intent: string; actor: string; ts: string }[]
}

/** What a projection-changing op wrote into the checked-out files. */
export interface Projected {
  projected: { written: string[]; removed: string[] } | null
}

export interface EditedCell {
  slug: string
  branch: string
  /** The base an editor carries into its next `cells.edit`. Never printed. */
  definition_hash: string
  /** Whether this lane was checked out and its files were projected. */
  written_to_files: boolean
  flags: { code: FlagCode; detail: string | null }[]
}

export interface ReorderedCell {
  slug: string
  uid: string
  branch: string
  /** Decimal text: converting this to a number can collapse adjacent midpoints. */
  order: string
}

/**
 * What leaving a run did. `stopped` is false when other branches were still
 * waiting on it — this branch left, the run keeps going, and no surface gets to
 * report a cancellation that did not happen.
 */
export interface Abandoned {
  branch: string
  /** How many in-flight runs this branch was waiting on. */
  left: number
  stopped: boolean
  /** Branches still waiting, when this one leaving was not the last. */
  awaiting: number
}

export interface EnvReport {
  workspace: string
  python: { path: string; source: string }
  packages: { name: string; version: string }[]
  flows: {
    flow: string
    kernel: 'running' | 'stopped'
    restart_required: boolean
    behind: string[]
  }[]
}

/**
 * The verbs the workbench drives. Adding one is a line here; a verb absent
 * from this map is a verb no surface in this build can call by accident.
 */
export interface FlowMethods {
  ping: Method<Record<string, never>, PingResult>
  status: Method<FlowScoped & { directory?: string }, WorkspaceStatus>
  context: Method<BranchScoped, ContextBrief>
  tree: Method<FlowScoped, BranchTree>
  /** 2–5 branches; the daemon refuses fewer and more, and names how many. */
  diff: Method<FlowScoped & { branches: string[] }, BranchDiff>
  /** A read: the branch's slice as one file, written nowhere by itself. */
  export: Method<BranchScoped, FlowExport>
  'workspace.list': Method<{ directory?: string }, WorkspaceListing>
  /** Scaffolds the flow unbound; the checkout below is what `init here` adds. */
  'flow.init': Method<{ name: string; directory?: string }, FlowBrief & { warnings: string[] }>
  'flow.checkout': Method<Intentful, Projected & FlowBrief>
  'flow.open': Method<FlowScoped & { worktree?: boolean }, FlowStatus>
  'cells.list': Method<BranchScoped & { unsynced?: boolean }, CellsPage>
  'cells.show': Method<BranchScoped & { slug: string }, CellDetail>
  'cells.logs': Method<BranchScoped & { slug: string }, CellLogs>
  'asset.preview': Method<BranchScoped & { target: string }, AssetView>
  /** The first gesture that starts a kernel — the surface says so before it does. */
  'asset.page': Method<
    BranchScoped & { target: string; query?: { offset?: number; limit?: number } },
    AssetPage
  >
  'cells.new': Method<
    Intentful & {
      slug?: string
      after?: string
      anchor?: string
      docstring?: string
      source?: string
      outputs?: 'all'
    },
    EditedCell
  >
  'cells.reorder': Method<
    BranchScoped & { slug: string; before?: string; after?: string },
    ReorderedCell
  >
  'cells.edit': Method<
    Intentful & { slug: string; source: string; base: string; force?: boolean },
    EditedCell
  >
  'cells.delete': Method<
    Intentful & { slug: string },
    Projected & { slug: string; branch: string; dangling: string[] }
  >
  /** The per-asset opt-in out of the cost threshold; lives in `flow.yaml`. */
  'cells.eager': Method<
    BranchScoped & { slug: string; eager: boolean },
    { flow: string; branch: string; slug: string; eager: boolean }
  >
  run: Method<Intentful & { target?: string; force?: boolean }, RunOutcome>
  /** `targets` is one closure over several leaves — what rerunning a branch costs. */
  preflight: Method<BranchScoped & { target?: string; targets?: string[] }, Preflight>
  cancel: Method<BranchScoped, Abandoned>
  fork: Method<
    Intentful & { name: string; from_branch?: string },
    {
      branch: string
      from_branch: string
      forked_at_step: number
      parent_step: number
      cells: number
    }
  >
  switch: Method<Intentful & { branch: string }, Projected & FlowBrief>
  rewind: Method<
    Intentful & { to_step: number },
    Projected & FlowBrief & { rewound_branch: string; to_step: number; cells: number }
  >
  /**
   * Mark a step on a branch. A marker, not a snapshot and not a step: the
   * store already keeps every version the step resolved to, so the intent is
   * the whole payload, and it attaches to the step itself — the branch's
   * newest one unless `step` names another — the way a commit message rides
   * on its commit. It comes back as the branch's `checkpoint` in the brief.
   */
  checkpoint: Method<
    Intentful & { step?: number },
    { branch: string; step: number; intent: string; ts: string; settled: boolean }
  >
  adopt: Method<
    Intentful & { slug: string; from_branch: string; force?: boolean },
    Projected & { slug: string; branch: string; rebound: string[] }
  >
  archive: Method<Intentful & { branch: string }, { branch: string; archived: boolean }>
  rename: Method<
    Intentful & { slug: string; to: string },
    Projected & { slug: string; renamed_from: string; branch: string; rewired: string[] }
  >
  'agents.harnesses': Method<Record<string, never>, { harnesses: AgentHarness[] }>
  'agents.setup': Method<{ harness: string; consent: boolean }, AgentHarness>
  'agents.remove': Method<{ harness: string }, AgentHarness>
  /** Stored cell context, including a trimmed traceback when the cell failed. */
  'agent.payload': Method<BranchScoped & { slug: string }, CellContextPayload>
  /** A read against a branch's values — never a version, never a journal line. */
  eval: Method<BranchScoped & { code: string }, EvalResult>
  /** Config, not history: the settings the panel renders, journaled nowhere. */
  'settings.set': Method<
    FlowScoped & Partial<FlowSettingsReport>,
    { flow: string; settings: FlowSettingsReport }
  >
  /** Workspace-scoped: one venv, every flow under it. */
  'env.status': Method<Record<string, never>, EnvReport>
  'kernel.restart': Method<FlowScoped, { flow: string; kernel: KernelReport }>
  'journal.since': Method<FlowScoped & { cursor: number }, JournalPage>
}

export type FlowMethod = keyof FlowMethods

export interface FlowApiOptions {
  /** Same origin by default: the daemon serves the SPA off the port it answers on. */
  baseUrl?: string
  token: string
  fetch?: typeof globalThis.fetch
}

export class FlowApi {
  private readonly baseUrl: string
  private readonly token: string
  private readonly transport: typeof globalThis.fetch

  constructor(options: FlowApiOptions) {
    this.baseUrl = options.baseUrl ?? ''
    this.token = options.token
    this.transport = options.fetch ?? globalThis.fetch.bind(globalThis)
  }

  async call<M extends FlowMethod>(
    method: M,
    params: FlowMethods[M]['params'],
  ): Promise<FlowMethods[M]['result']> {
    let answer: Response
    try {
      answer = await this.transport(`${this.baseUrl}${RPC_PATH}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', [TOKEN_HEADER]: this.token },
        body: JSON.stringify({ method, params }),
      })
    } catch (unreachable) {
      throw new DaemonUnreachable(method, unreachable)
    }
    const body: unknown = await answer.json().catch(() => null)
    // A refused token is neither of the two: somebody answered, and nothing is
    // wrong with the request. Dropping it here — at the one door every verb
    // crosses — is what lets the surfaces render "not connected" once instead
    // of each gesture repeating a sentence the reader cannot act on.
    if (answer.status === UNAUTHORIZED) rejectToken()
    const error = readError(body)
    if (error !== null) {
      throw new FlowApiError(error.message, { kind: error.kind, status: answer.status })
    }
    if (!answer.ok) {
      throw new FlowApiError(`lumlflow refused \`${method}\``, { status: answer.status })
    }
    return (body as { result: FlowMethods[M]['result'] }).result
  }

  downloadUrl(params: { flow: string; branch: string; target: string }): string {
    const query = new URLSearchParams({ token: this.token, ...params })
    return `${this.baseUrl}${DOWNLOAD_PATH}?${query.toString()}`
  }
}

function readError(body: unknown): { message: string; kind?: string } | null {
  if (typeof body !== 'object' || body === null || !('error' in body)) return null
  const error = (body as { error: unknown }).error
  if (typeof error !== 'object' || error === null) return null
  const { message, kind } = error as { message?: unknown; kind?: unknown }
  return {
    message: typeof message === 'string' ? message : 'lumlflow refused this',
    kind: typeof kind === 'string' ? kind : undefined,
  }
}
