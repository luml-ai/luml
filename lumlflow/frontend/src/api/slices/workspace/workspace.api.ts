import { api } from '@/api/client'
import type {
  AgentHarness,
  ExperimentPublishOptions,
  PublishedAsset,
  PublishedExperiment,
  PublishTarget,
} from '@/flow/api/types'
import type {
  AssetPreview,
  BranchTree,
  CancelledRun,
  CellContextPayload,
  CheckpointedBranch,
  CellDetail,
  CellLogs,
  CellsPage,
  CreatedFlow,
  DeletedCell,
  DeletedFlow,
  DuplicatedFlow,
  EditedCell,
  EndedAgentSession,
  ForkedBranch,
  FlowSettingsReport,
  JournalPage,
  NewCell,
  OpenedFlow,
  RanCell,
  RanLane,
  RenamedCell,
  RenamedFlow,
  RewoundBranch,
  SavedSettings,
  SwitchedBranch,
  WorkspaceListing,
} from './workspace.interface'

const RPC_PATH = 'flow/rpc'
const TOKEN_HEADER = 'x-lumlflow-token'
const TOKEN_STORAGE_KEY = 'lumlflow.flow.token'
const UNAUTHORIZED = 401

interface RpcError {
  message: string
  kind?: string
}

interface RpcResponse<R> {
  result?: R
  error?: RpcError
}

export class WorkspaceUnauthorizedError extends Error {
  constructor() {
    super("this workspace's key is required. open the address `lumlflow ui` prints")
    this.name = 'WorkspaceUnauthorizedError'
  }
}

export class WorkspaceRefusedError extends Error {
  readonly kind: string | undefined

  constructor(message: string, kind?: string) {
    super(message)
    this.name = 'WorkspaceRefusedError'
    this.kind = kind
  }
}

export class WorkspaceUnreachableError extends Error {
  constructor() {
    super('lumlflow daemon is not reachable')
    this.name = 'WorkspaceUnreachableError'
  }
}

function getDaemonToken(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(TOKEN_STORAGE_KEY)
}

async function call<P, R>(method: string, params: P): Promise<R> {
  const token = getDaemonToken()
  if (!token) throw new WorkspaceUnauthorizedError()

  let response
  try {
    response = await api.post<RpcResponse<R>>(
      RPC_PATH,
      { method, params },
      {
        headers: { [TOKEN_HEADER]: token },
        validateStatus: () => true,
      },
    )
  } catch {
    throw new WorkspaceUnreachableError()
  }

  if (response.status === UNAUTHORIZED) throw new WorkspaceUnauthorizedError()
  const refused = response.data.error
  if (refused) throw new WorkspaceRefusedError(refused.message, refused.kind)
  if (response.status < 200 || response.status >= 300) {
    throw new Error(`lumlflow refused \`${method}\``)
  }
  return response.data.result as R
}

export const workspaceApi = {
  listFlows: (directory?: string) => {
    return call<{ directory?: string }, WorkspaceListing>(
      'workspace.list',
      directory ? { directory } : {},
    )
  },

  createFlow: (name: string, directory: string) =>
    call<{ name: string; directory: string }, CreatedFlow>('flow.init', { name, directory }),

  checkoutFlow: (flow: string, intent: string) =>
    call<{ flow: string; branch: string; intent: string }, unknown>('flow.checkout', {
      flow,
      branch: 'main',
      intent,
    }),

  renameFlow: (flow: string, name: string) =>
    call<{ flow: string; name: string }, RenamedFlow>('flow.rename', { flow, name }),

  deleteFlow: (flow: string) => call<{ flow: string }, DeletedFlow>('flow.delete', { flow }),

  duplicateFlow: (flow: string, name: string) =>
    call<{ flow: string; name: string }, DuplicatedFlow>('flow.duplicate', { flow, name }),

  tree: (flow?: string) => call<{ flow?: string }, BranchTree>('tree', flow ? { flow } : {}),

  switchBranch: (branch: string, intent: string, flow?: string) =>
    call<{ flow?: string; branch: string; intent: string }, SwitchedBranch>('switch', {
      ...(flow ? { flow } : {}),
      branch,
      intent,
    }),

  forkBranch: (name: string, from: string, flow?: string) =>
    call<
      { flow?: string; branch: string; name: string; from_branch: string; intent: string },
      ForkedBranch
    >('fork', {
      ...(flow ? { flow } : {}),
      branch: from,
      name,
      from_branch: from,
      intent: `started ${name} from ${from}`,
    }),

  rewindBranch: (branch: string, toStep: number, flow?: string) =>
    call<{ flow?: string; branch: string; to_step: number; intent: string }, RewoundBranch>(
      'rewind',
      {
        ...(flow ? { flow } : {}),
        branch,
        to_step: toStep,
        intent: `moved ${branch} to step ${toStep}`,
      },
    ),

  checkpointBranch: (branch: string, intent: string, flow?: string, step?: number) =>
    call<{ flow?: string; branch: string; intent: string; step?: number }, CheckpointedBranch>(
      'checkpoint',
      {
        ...(flow ? { flow } : {}),
        ...(step !== undefined ? { step } : {}),
        branch,
        intent,
      },
    ),

  cellsList: (flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string }, CellsPage>('cells.list', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
    }),

  assetPreview: (target: string, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; target: string }, AssetPreview>('asset.preview', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      target,
    }),

  publishAsset: (target: string, destination: PublishTarget, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; target: string } & PublishTarget, PublishedAsset>(
      'asset.publish',
      {
        ...(flow ? { flow } : {}),
        ...(branch ? { branch } : {}),
        target,
        ...destination,
      },
    ),

  publishExperiment: (
    target: string,
    destination: PublishTarget,
    options: ExperimentPublishOptions,
    flow?: string,
    branch?: string,
  ) =>
    call<
      { flow?: string; branch?: string; target: string } & PublishTarget & ExperimentPublishOptions,
      PublishedExperiment
    >('experiment.publish', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      target,
      ...destination,
      ...options,
    }),

  journalSince: (flow?: string, cursor = 0) =>
    call<{ flow?: string; cursor: number }, JournalPage>('journal.since', {
      ...(flow ? { flow } : {}),
      cursor,
    }),

  renameCell: (slug: string, to: string, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; slug: string; to: string }, RenamedCell>('rename', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      slug,
      to,
    }),

  cellSource: (slug: string, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; slug: string }, CellDetail>('cells.show', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      slug,
    }),

  cellLogs: (slug: string, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; slug: string }, CellLogs>('cells.logs', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      slug,
    }),

  editCell: (
    slug: string,
    source: string,
    flow?: string,
    branch?: string,
    lock: { base?: string; force?: boolean } = {},
  ) =>
    call<
      {
        flow?: string
        branch?: string
        slug: string
        source: string
        base?: string
        force?: boolean
      },
      EditedCell
    >('cells.edit', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      slug,
      source,
      ...(lock.base ? { base: lock.base } : {}),
      ...(lock.force ? { force: true } : {}),
    }),

  newCell: (params: {
    slug?: string
    source?: string
    after?: string
    flow?: string
    branch?: string
  }) =>
    call<
      {
        flow?: string
        branch?: string
        slug?: string
        source?: string
        after?: string
      },
      NewCell
    >('cells.new', {
      ...(params.flow ? { flow: params.flow } : {}),
      ...(params.branch ? { branch: params.branch } : {}),
      ...(params.slug ? { slug: params.slug } : {}),
      ...(params.source ? { source: params.source } : {}),
      ...(params.after ? { after: params.after } : {}),
    }),

  deleteCell: (slug: string, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; slug: string }, DeletedCell>('cells.delete', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      slug,
    }),

  endAgentSession: (actor: string, flow?: string) =>
    call<{ flow?: string; actor: string }, EndedAgentSession>('agent.end', {
      ...(flow ? { flow } : {}),
      actor,
    }),

  agentHarnesses: () =>
    call<Record<string, never>, { harnesses: AgentHarness[] }>('agents.harnesses', {}),

  setupAgentHarness: (harness: string, consent: boolean) =>
    call<{ harness: string; consent: boolean }, AgentHarness>('agents.setup', {
      harness,
      consent,
    }),

  removeAgentHarness: (harness: string) =>
    call<{ harness: string }, AgentHarness>('agents.remove', { harness }),

  agentPayload: (slug: string, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; slug: string }, CellContextPayload>('agent.payload', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      slug,
    }),

  runLane: (flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string }, RanLane>('run', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
    }),

  runCell: (target: string, flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string; target: string }, RanCell>('run', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
      target,
    }),

  cancelRun: (flow?: string, branch?: string) =>
    call<{ flow?: string; branch?: string }, CancelledRun>('cancel', {
      ...(flow ? { flow } : {}),
      ...(branch ? { branch } : {}),
    }),

  openFlow: (flow?: string) =>
    call<{ flow?: string }, OpenedFlow>('flow.open', {
      ...(flow ? { flow } : {}),
    }),

  getSettings: (flow?: string) =>
    call<{ flow?: string }, SavedSettings>('settings.get', {
      ...(flow ? { flow } : {}),
    }),

  setSettings: (settings: Partial<FlowSettingsReport>, flow?: string) =>
    call<{ flow?: string } & Partial<FlowSettingsReport>, SavedSettings>('settings.set', {
      ...(flow ? { flow } : {}),
      ...settings,
    }),
}
