import type {
  AgentHarness,
  AssetPage,
  AssetView,
  BranchDiff,
  BranchRecord,
  CellContextPayload,
  CellDetail,
  CellLogs,
  ExperimentPublishOptions,
  CellSummary,
  FlagCode,
  FlowBrief,
  FlowExport,
  FlowSettingsReport,
  FlowStatus,
  JournalPage,
  KernelReport,
  OpenFlowsListing,
  Preflight,
  PublishTarget,
  PublishedAsset,
  PublishedExperiment,
  RunOutcome,
  StaleState,
  WorkspaceStatus,
} from './types'
import { rejectToken } from './token'

export const RPC_PATH = '/api/flow/rpc'
export const DOWNLOAD_PATH = '/api/flow/download'
export const TOKEN_HEADER = 'x-lumlflow-token'

const UNAUTHORIZED = 401

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
  flow?: string
}

export interface BranchScoped extends FlowScoped {
  branch?: string
}

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

export interface Projected {
  projected: { written: string[]; removed: string[] } | null
}

export interface EditedCell {
  slug: string
  branch: string
  definition_hash: string
  written_to_files: boolean
  flags: { code: FlagCode; detail: string | null }[]
}

export interface ReorderedCell {
  slug: string
  uid: string
  branch: string
  order: string
}

export interface Abandoned {
  branch: string
  left: number
  stopped: boolean
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

export interface FlowMethods {
  ping: Method<Record<string, never>, PingResult>
  status: Method<FlowScoped & { directory?: string }, WorkspaceStatus>
  context: Method<BranchScoped, ContextBrief>
  tree: Method<FlowScoped, BranchTree>
  diff: Method<FlowScoped & { branches: string[] }, BranchDiff>
  export: Method<BranchScoped, FlowExport>
  'workspace.list': Method<{ directory?: string }, WorkspaceListing>
  'flows.open': Method<{ directory?: string }, OpenFlowsListing>
  'flow.init': Method<{ name: string; directory?: string }, FlowBrief & { warnings: string[] }>
  'flow.checkout': Method<Intentful, Projected & FlowBrief>
  'flow.open': Method<FlowScoped & { worktree?: boolean }, FlowStatus>
  'cells.list': Method<BranchScoped & { unsynced?: boolean }, CellsPage>
  'cells.show': Method<BranchScoped & { slug: string }, CellDetail>
  'cells.logs': Method<BranchScoped & { slug: string }, CellLogs>
  'asset.preview': Method<BranchScoped & { target: string }, AssetView>
  'asset.page': Method<
    BranchScoped & { target: string; query?: { offset?: number; limit?: number } },
    AssetPage
  >
  'asset.publish': Method<BranchScoped & { target: string } & PublishTarget, PublishedAsset>
  'experiment.publish': Method<
    BranchScoped & { target: string } & PublishTarget & ExperimentPublishOptions,
    PublishedExperiment
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
  'cells.eager': Method<
    BranchScoped & { slug: string; eager: boolean },
    { flow: string; branch: string; slug: string; eager: boolean }
  >
  run: Method<Intentful & { target?: string; force?: boolean }, RunOutcome>
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
  'agent.payload': Method<BranchScoped & { slug: string }, CellContextPayload>
  'settings.get': Method<FlowScoped, { flow: string; settings: FlowSettingsReport }>
  'settings.set': Method<
    FlowScoped & Partial<FlowSettingsReport>,
    { flow: string; settings: FlowSettingsReport }
  >
  'env.status': Method<{ directory?: string }, EnvReport>
  'kernel.restart': Method<FlowScoped, { flow: string; kernel: KernelReport }>
  'journal.since': Method<FlowScoped & { cursor: number }, JournalPage>
}

export type FlowMethod = keyof FlowMethods

export interface FlowApiOptions {
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
