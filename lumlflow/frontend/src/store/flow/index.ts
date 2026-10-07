import type {
  AssetPreview,
  BranchRecord,
  CancelledRun,
  CellSummary,
  JournalTransaction,
  RanCell,
  RanLane,
} from '@/api/slices/workspace/workspace.interface'
import type {
  AgentSessionRecord,
  ExperimentPublishOptions,
  PublishedAsset,
  PublishedExperiment,
  PublishTarget,
} from '@/flow/api/types'
import type { INotebookLane, INotebookLaneNode } from '@/components/notebooks/lanes/interface'
import type {
  NotebookAssetInterface,
  NotebookAssetType,
} from '@/components/notebooks/notebooks.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useToast } from 'primevue'
import { errorToast } from '@/toasts'
import { formatUpdatedAgo } from '@/helpers/date'
import { compareOrder } from './order'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { FlowStream, streamToken } from '@/api/streams/flow'
import type { AgentActivity, AgentClaim, StreamFrame } from '@/api/streams/flow'

export interface ExperimentUploadTarget {
  slug: string
  output: string
  experimentId: string
  /** The cell's `model` outputs, which go when the tracker links no models. */
  models: string[]
}

export interface CellEditContext {
  flow: string | undefined
  branch: string
  base: string
}

export interface LiveRun {
  run_id: string
  slug: string
  phase: 'queued' | 'running'
}

export type CellLiveState =
  | { kind: 'running'; run_id: string }
  | { kind: 'queued'; run_id: string }
  | {
      kind: 'agent'
      actor: string
      label: string
      tool: string | null
      inCall: boolean
      active: boolean
      color: string
    }

export const AGENT_COLORS = [
  'var(--p-blue-500)',
  'var(--p-orange-500)',
  'var(--p-purple-500)',
  'var(--p-teal-500)',
  'var(--p-pink-500)',
  'var(--p-green-500)',
]

export const DEFAULT_CLAIM_IDLE_MS = 180_000

export const AGENT_ACTIVE_MS = 30_000

export interface PairedAgent {
  actor: string
  label: string
  color: string
  slug: string | null
  tool: string | null
}

function formatStepCount(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

function toLane(record: BranchRecord): INotebookLane {
  return {
    id: record.branch,
    name: record.branch,
    steps: record.cells,
    updatedAgo: formatUpdatedAgo(record.last_intent?.ts ?? null),
    parentId: record.parent,
    state: record.archived ? 'inactive' : 'active',
    current: record.checked_out,
  }
}

const NOT_A_POSITION_OPS = new Set([
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

function isPosition(transaction: JournalTransaction): boolean {
  if (transaction.actor === 'auto') return false
  if (!transaction.ops.length) return true
  return !transaction.ops.every((op) => NOT_A_POSITION_OPS.has(op.op))
}

function isPointMark(transaction: JournalTransaction): boolean {
  return transaction.ops.length > 0 && transaction.ops.every((op) => op.op === 'checkpointed')
}

function assetTypeFromKind(kind: string | undefined): NotebookAssetType {
  switch (kind) {
    case 'dataset':
      return 'dataset'
    case 'experiment':
      return 'experiment'
    case 'model':
      return 'model'
    case 'plot':
      return 'graph'
    default:
      return 'unknown'
  }
}

function toNotebookCell(cell: CellSummary): NotebookAssetInterface {
  const kind = cell.primary ? cell.kinds[cell.primary] : undefined
  return {
    id: cell.slug,
    type: assetTypeFromKind(kind),
    name: cell.slug,
    unmaterialized: cell.state === 'unmaterialized',
  }
}

function buildLaneTree(records: BranchRecord[]): INotebookLaneNode[] {
  const lanes = records.map(toLane)
  const nodes = new Map<string, INotebookLaneNode>(
    lanes.map((lane) => [lane.id, { ...lane, children: [] }]),
  )
  const roots: INotebookLaneNode[] = []

  for (const lane of lanes) {
    const node = nodes.get(lane.id)
    if (!node) continue
    const parent = lane.parentId ? nodes.get(lane.parentId) : undefined
    if (parent) {
      parent.children.push(node)
    } else {
      roots.push(node)
    }
  }

  return roots
}

export const useFlowStore = defineStore('flow', () => {
  const toast = useToast()

  const isSidebarOpened = ref(true)
  const viewMode = ref<'canvas' | 'notebook'>('canvas')

  const reactivity = ref<'lazy' | 'auto'>('auto')
  const autoThresholdSeconds = ref(5)

  const branches = ref<BranchRecord[]>([])
  const currentFlow = ref<string | null>(null)
  const isBranchesLoading = ref(false)
  const isSwitchingBranch = ref(false)

  const cells = ref<CellSummary[]>([])
  const isCellsLoading = ref(false)

  const journal = ref<JournalTransaction[]>([])
  const isJournalLoading = ref(false)

  const isLaneForkPromptVisible = ref(false)

  const selectedCellId = ref<string | null>(null)
  const expandedCellId = ref<string | null>(null)
  const uploadExperimentTarget = ref<ExperimentUploadTarget | null>(null)
  const uploadModelTarget = ref<{ slug: string; output: string } | null>(null)
  const experimentRemovals = ref<Record<string, number>>({})

  const laneTree = computed(() => buildLaneTree(branches.value))
  const currentBranch = computed(() => branches.value.find((branch) => branch.checked_out) ?? null)
  const agentSessions = ref<AgentSessionRecord[]>([])
  const leasedSessions = computed(() =>
    currentBranch.value?.checked_out
      ? agentSessions.value
          .filter((session) => session.leased)
          .sort((left, right) => left.begun_step - right.begun_step)
      : [],
  )
  const pairedAgent = computed(() => leasedSessions.value[0] ?? null)
  const pairedAgentLabel = computed(() => pairedAgent.value?.label ?? null)
  function agentColor(actor: string): string {
    const at = leasedSessions.value.findIndex((session) => session.actor === actor)
    return AGENT_COLORS[Math.max(at, 0) % AGENT_COLORS.length] as string
  }
  const liveRuns = ref<LiveRun[]>([])
  const agentClaims = ref<AgentClaim[]>([])
  const claimIdleMs = ref(DEFAULT_CLAIM_IDLE_MS)
  const claimIdleMinutes = computed(() => claimIdleMs.value / 60_000)
  const agentCalls = ref<Record<string, AgentActivity>>({})
  // A claim lapses on its own, unannounced, and this is the clock the card
  // lets go by. It ticks only while there is a claim to lapse.
  const now = ref(Date.now())
  let claimClock: ReturnType<typeof setInterval> | null = null
  function keepClock() {
    const wanted = agentClaims.value.length > 0
    if (wanted && claimClock === null) {
      claimClock = setInterval(() => {
        now.value = Date.now()
      }, 5_000)
    } else if (!wanted && claimClock !== null) {
      clearInterval(claimClock)
      claimClock = null
    }
  }
  function setClaims(claims: AgentClaim[]) {
    agentClaims.value = claims
    now.value = Date.now()
    keepClock()
  }
  const liveClaims = computed(() => {
    const branchId = currentBranch.value?.branch_id
    return agentClaims.value.filter(
      (claim) => claim.branch_id === branchId && now.value - claim.last < claimIdleMs.value,
    )
  })
  function callOn(actor: string, slug: string | null): AgentActivity | null {
    const call = agentCalls.value[actor]
    if (!call) return null
    return slug === null || call.slug === null || call.slug === slug ? call : null
  }
  const pairedAgents = computed<PairedAgent[]>(() =>
    leasedSessions.value.map((session) => {
      const claim = liveClaims.value.find((held) => held.actor === session.actor)
      const slug = claim?.slug ?? null
      return {
        actor: session.actor,
        label: session.label,
        color: agentColor(session.actor),
        slug,
        tool: callOn(session.actor, slug)?.tool ?? null,
      }
    }),
  )
  const cellLiveStates = computed<Record<string, CellLiveState>>(() => {
    const states: Record<string, CellLiveState> = {}
    for (const claim of liveClaims.value) {
      const call = agentCalls.value[claim.actor]
      const onThis = call !== undefined && call.slug === claim.slug
      states[claim.slug] = {
        kind: 'agent',
        actor: claim.actor,
        label: claim.label,
        tool: onThis ? call.tool : null,
        inCall: onThis,
        active: onThis || now.value - claim.last < AGENT_ACTIVE_MS,
        color: agentColor(claim.actor),
      }
    }
    for (const run of liveRuns.value) {
      const held = states[run.slug]
      if (run.phase === 'queued' && held?.kind === 'running') continue
      states[run.slug] = { kind: run.phase, run_id: run.run_id }
    }
    return states
  })
  const isAnythingRunning = computed(() => liveRuns.value.length > 0)
  const notebookCells = computed(() =>
    [...cells.value].sort((a, b) => compareOrder(a.order, b.order)).map(toNotebookCell),
  )
  const currentBranchActivities = computed(() => {
    const branchId = currentBranch.value?.branch_id
    if (!branchId) return []
    return journal.value
      .filter((transaction) => transaction.branch === branchId)
      .sort((a, b) => b.step - a.step)
  })

  const currentBranchSteps = computed(() => currentBranchActivities.value.filter(isPosition))

  const currentBranchPoints = computed(() => {
    const points = new Map<number, string>()
    let lastPositionStep: number | undefined
    for (const transaction of [...currentBranchActivities.value].reverse()) {
      if (isPointMark(transaction)) {
        // Marks written before they folded name no step and ride the position before them.
        const step = transaction.ops[0]?.step ?? lastPositionStep
        if (step !== undefined) points.set(step, transaction.intent)
        continue
      }
      if (isPosition(transaction)) lastPositionStep = transaction.step
    }
    return points
  })

  const currentHeadStep = computed(() => {
    console.log(currentBranch.value)
    return currentBranch.value?.head_step ?? null
  })

  // After a rewind the lane stands behind its newest step; changing state there
  // would rewrite its history, so a change has to go on a new lane instead.
  const isBehindLaneHead = computed(() => {
    const branch = currentBranch.value
    return !!branch && branch.head_step < branch.newest_step
  })

  const currentBranchFamilyLine = computed(() => {
    const branch = currentBranch.value
    if (!branch || currentHeadStep.value === null) return ''
    if (branch.parent === null || branch.parent_step === null) return 'root lane'
    return `started from ${branch.parent} · ${formatStepCount(currentHeadStep.value - branch.parent_step, 'step')} ago`
  })

  function ensureOnLaneHead(): boolean {
    if (!isBehindLaneHead.value) return true
    isLaneForkPromptVisible.value = true
    return false
  }

  function setLaneForkPromptVisible(visible: boolean) {
    isLaneForkPromptVisible.value = visible
  }

  function toggleSidebar() {
    isSidebarOpened.value = !isSidebarOpened.value
  }

  function selectCell(id: string | null) {
    selectedCellId.value = id
  }

  function setExpandedCellId(id: string | null) {
    expandedCellId.value = id
  }

  function setUploadExperimentTarget(target: ExperimentUploadTarget | null) {
    uploadExperimentTarget.value = target
  }

  function setUploadModelTarget(target: { slug: string; output: string } | null) {
    uploadModelTarget.value = target
  }

  async function publishModel(destination: PublishTarget): Promise<PublishedAsset> {
    const target = uploadModelTarget.value
    if (!target) throw new Error('No model selected to promote')
    return workspaceApi.publishAsset(
      `${target.slug}.${target.output}`,
      destination,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
  }

  async function publishExperiment(
    destination: PublishTarget,
    options: ExperimentPublishOptions,
  ): Promise<PublishedExperiment> {
    const target = uploadExperimentTarget.value
    if (!target) throw new Error('No experiment selected to promote')
    return workspaceApi.publishExperiment(
      `${target.slug}.${target.output}`,
      destination,
      options,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
  }

  async function endAgentSession(actor: string) {
    await workspaceApi.endAgentSession(actor, currentFlow.value ?? undefined)
    await fetchBranches()
  }

  function setViewMode(mode: 'canvas' | 'notebook') {
    viewMode.value = mode
  }

  function applySettings(settings: {
    reactivity: 'lazy' | 'auto'
    eager_cost_threshold_s: number
  }) {
    reactivity.value = settings.reactivity
    autoThresholdSeconds.value = settings.eager_cost_threshold_s
  }

  async function fetchSettings() {
    try {
      const saved = await workspaceApi.getSettings(currentFlow.value ?? undefined)
      applySettings(saved.settings)
    } catch (error) {
      toast.add(errorToast(error, 'Failed to load reactivity settings'))
    }
  }

  async function setReactivity(mode: 'lazy' | 'auto') {
    try {
      const saved = await workspaceApi.setSettings(
        { reactivity: mode },
        currentFlow.value ?? undefined,
      )
      applySettings(saved.settings)
    } catch (error) {
      toast.add(errorToast(error, 'Failed to update reactivity'))
    }
  }

  async function setAutoThresholdSeconds(seconds: number) {
    try {
      const saved = await workspaceApi.setSettings(
        { eager_cost_threshold_s: seconds },
        currentFlow.value ?? undefined,
      )
      applySettings(saved.settings)
    } catch (error) {
      toast.add(errorToast(error, 'Failed to update auto-run threshold'))
    }
  }

  let cascadeStream: FlowStream | null = null
  let stopCascadeFrame: (() => void) | null = null
  let cascadeSettleTimer: ReturnType<typeof setTimeout> | null = null

  function scheduleLiveRefetch() {
    if (cascadeSettleTimer !== null) clearTimeout(cascadeSettleTimer)
    cascadeSettleTimer = setTimeout(() => {
      cascadeSettleTimer = null
      void fetchBranches()
    }, 250)
  }

  function disconnectCascadeStream() {
    setClaims([])
    agentCalls.value = {}
    stopCascadeFrame?.()
    stopCascadeFrame = null
    cascadeStream?.close()
    cascadeStream = null
    if (cascadeSettleTimer !== null) {
      clearTimeout(cascadeSettleTimer)
      cascadeSettleTimer = null
    }
  }

  async function connectCascadeStream(flow: string) {
    disconnectCascadeStream()
    const token = streamToken()
    if (!token) return
    try {
      const opened = await workspaceApi.openFlow(flow)
      const stream = new FlowStream({ token })
      cascadeStream = stream
      stopCascadeFrame = stream.onFrame((frame: StreamFrame) => {
        if (!('channel' in frame) || frame.channel !== 'journal') return
        if (frame.type === 'lagged' || frame.flow !== opened.path) return
        receiveLiveFrame(frame)
      })
      stream.connect()
      stream.watchJournal(opened.path, opened.flow_id)
    } catch (error) {
      toast.add(errorToast(error, 'Failed to open a live connection for cell updates'))
    }
  }

  function receiveLiveFrame(frame: StreamFrame) {
    if (!('channel' in frame) || frame.channel !== 'journal') return
    if (frame.type === 'lagged') return
    if (frame.type === 'state') {
      receiveStateFrame(frame)
      return
    }
    if (frame.type === 'agents') {
      // The whole list at that moment, lease state included — replace it.
      // Nothing else in the tree moved, so no refetch is owed for it. An
      // agent whose lease is gone holds nothing and is in no call; the
      // daemon's own claims frame follows, this only gets there first.
      agentSessions.value = frame.sessions
      const leased = new Set(
        frame.sessions.filter((session) => session.leased).map((session) => session.actor),
      )
      setClaims(agentClaims.value.filter((claim) => leased.has(claim.actor)))
      agentCalls.value = Object.fromEntries(
        Object.entries(agentCalls.value).filter(([actor]) => leased.has(actor)),
      )
      return
    }
    if (frame.type === 'claims') {
      claimIdleMs.value = frame.idle_after_s * 1000
      setClaims(frame.claims)
      return
    }
    if (frame.type === 'activity') {
      const calls = { ...agentCalls.value }
      if (frame.phase === 'started') {
        calls[frame.actor] = {
          actor: frame.actor,
          label: frame.label,
          tool: frame.tool,
          slug: frame.slug,
        }
      } else {
        delete calls[frame.actor]
      }
      agentCalls.value = calls
      return
    }
    if (frame.type === 'caught_up') {
      liveRuns.value = frame.running.map((entry) => ({
        run_id: entry.run_id,
        slug: entry.slug,
        phase: 'running',
      }))
      if (frame.claim_idle_s) claimIdleMs.value = frame.claim_idle_s * 1000
      setClaims(frame.claims ?? [])
      agentCalls.value = Object.fromEntries(
        (frame.activity ?? []).map((entry) => [entry.actor, entry]),
      )
      scheduleLiveRefetch()
      return
    }
    if (frame.type === 'kernel') {
      receiveKernelFrame(frame)
      scheduleLiveRefetch()
      return
    }
    if (frame.type === 'transaction' && rewindsCurrentLane(frame.transaction.ops)) {
      leaveMovedLane()
    }
    scheduleLiveRefetch()
  }

  function receiveStateFrame(frame: Extract<StreamFrame, { type: 'state' }>) {
    if (frame.state === 'order_changed') {
      scheduleLiveRefetch()
      return
    }
    if (frame.state !== 'experiment_removed') return
    if (!frame.lane || frame.lane !== currentBranch.value?.branch) return
    if (frame.cell) {
      experimentRemovals.value = {
        ...experimentRemovals.value,
        [frame.cell]: (experimentRemovals.value[frame.cell] ?? 0) + 1,
      }
    }
    scheduleLiveRefetch()
  }

  function rewindsCurrentLane(ops: unknown[]): boolean {
    const branchId = currentBranch.value?.branch_id
    if (!branchId) return false
    return ops.some((op) => {
      const held = op as { op?: string; branch_id?: string }
      return held.op === 'rewound' && held.branch_id === branchId
    })
  }

  function leaveMovedLane() {
    const branchId = currentBranch.value?.branch_id
    setClaims(agentClaims.value.filter((claim) => claim.branch_id !== branchId))
    agentCalls.value = {}
  }

  function receiveKernelFrame(frame: Extract<StreamFrame, { type: 'kernel' }>) {
    if (frame.event === 'kernel_state') {
      // A kernel that died mid-run reports no ending for it.
      if (frame.kernel === 'stopped') liveRuns.value = []
      return
    }
    if (!frame.run_id) return
    const runId = frame.run_id
    const others = liveRuns.value.filter((entry) => entry.run_id !== runId)
    if (frame.event === 'awaiting') {
      const held = liveRuns.value.find((entry) => entry.run_id === runId)
      if (frame.awaiting === 0) {
        liveRuns.value = others
      } else if (!held) {
        liveRuns.value = [...others, { run_id: runId, slug: frame.slug ?? '', phase: 'queued' }]
      }
      return
    }
    if (frame.event === 'started') {
      liveRuns.value = [...others, { run_id: runId, slug: frame.slug ?? '', phase: 'running' }]
      return
    }
    if (frame.event === 'materialized' || frame.event === 'failed') {
      liveRuns.value = others
    }
  }

  function setFlow(flow: string | null) {
    if (currentFlow.value === flow) return
    currentFlow.value = flow
    void fetchBranches()
    void fetchSettings()
    if (flow) {
      void connectCascadeStream(flow)
    } else {
      disconnectCascadeStream()
    }
  }

  async function fetchBranches() {
    isBranchesLoading.value = true
    try {
      const tree = await workspaceApi.tree(currentFlow.value ?? undefined)
      branches.value = tree.branches
      agentSessions.value = tree.agent_sessions ?? []
    } catch (error) {
      toast.add(errorToast(error, 'Failed to load branches'))
    } finally {
      isBranchesLoading.value = false
    }
    await Promise.all([fetchCells(), fetchJournal()])
  }

  async function fetchCells() {
    isCellsLoading.value = true
    try {
      const page = await workspaceApi.cellsList(
        currentFlow.value ?? undefined,
        currentBranch.value?.branch,
      )
      cells.value = page.cells
    } catch (error) {
      toast.add(errorToast(error, 'Failed to load cells'))
    } finally {
      isCellsLoading.value = false
    }
  }

  async function fetchJournal() {
    isJournalLoading.value = true
    try {
      const page = await workspaceApi.journalSince(currentFlow.value ?? undefined)
      journal.value = page.transactions
    } catch (error) {
      toast.add(errorToast(error, 'Failed to load activities'))
    } finally {
      isJournalLoading.value = false
    }
  }

  async function switchBranch(branch: string) {
    if (isSwitchingBranch.value || currentBranch.value?.branch === branch) return
    isSwitchingBranch.value = true
    try {
      await workspaceApi.switchBranch(
        branch,
        `put ${branch} on disk`,
        currentFlow.value ?? undefined,
      )
      await fetchBranches()
    } catch (error) {
      toast.add(errorToast(error, 'Failed to switch branch'))
    } finally {
      isSwitchingBranch.value = false
    }
  }

  async function renameCell(slug: string, to: string) {
    await workspaceApi.renameCell(
      slug,
      to,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    await fetchCells()
  }

  async function fetchCellSource(
    slug: string,
  ): Promise<{ source: string; context: CellEditContext }> {
    const flow = currentFlow.value ?? undefined
    const detail = await workspaceApi.cellSource(slug, flow, currentBranch.value?.branch)
    return {
      source: detail.source,
      context: { flow, branch: detail.branch, base: detail.definition_hash },
    }
  }

  async function fetchAssetPreview(slug: string, output?: string): Promise<AssetPreview> {
    const target = output ? `${slug}.${output}` : slug
    return workspaceApi.assetPreview(
      target,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
  }

  async function fetchCellLogs(slug: string): Promise<string | null> {
    const detail = await workspaceApi.cellLogs(
      slug,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    return detail.logs
  }

  async function copyCellContext(slug: string): Promise<string> {
    const payload = await workspaceApi.agentPayload(
      slug,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    return payload.text
  }

  async function editCellSource(
    slug: string,
    source: string,
    context: CellEditContext,
    options: { force?: boolean } = {},
  ) {
    await workspaceApi.editCell(slug, source, context.flow, context.branch, {
      base: context.base,
      force: options.force,
    })
    await fetchCells()
  }

  async function isLaneBehindHead(branch: string, flow?: string): Promise<boolean> {
    const tree = await workspaceApi.tree(flow)
    if (flow === (currentFlow.value ?? undefined)) branches.value = tree.branches
    const lane = tree.branches.find((record) => record.branch === branch)
    return !!lane && lane.head_step < lane.newest_step
  }

  function nextDuplicateSlug(slug: string): string {
    const taken = new Set(cells.value.map((cell) => cell.slug.toLowerCase()))
    let candidate = `${slug}_copy`
    let suffix = 2
    while (taken.has(candidate.toLowerCase())) {
      candidate = `${slug}_copy_${suffix}`
      suffix += 1
    }
    return candidate
  }

  async function duplicateCell(slug: string): Promise<string> {
    const flow = currentFlow.value ?? undefined
    const branch = currentBranch.value?.branch
    const detail = await workspaceApi.cellSource(slug, flow, branch)
    const created = await workspaceApi.newCell({
      slug: nextDuplicateSlug(slug),
      source: detail.source,
      after: slug,
      flow,
      branch,
    })
    await fetchCells()
    return created.slug
  }

  async function addCellDownstream(slug: string): Promise<string> {
    const created = await workspaceApi.newCell({
      after: slug,
      flow: currentFlow.value ?? undefined,
      branch: currentBranch.value?.branch,
    })
    await fetchCells()
    return created.slug
  }

  async function createCell(name: string): Promise<string> {
    const created = await workspaceApi.newCell({
      slug: name,
      flow: currentFlow.value ?? undefined,
      branch: currentBranch.value?.branch,
    })
    await fetchCells()
    return created.slug
  }

  async function deleteCell(slug: string) {
    await workspaceApi.deleteCell(slug, currentFlow.value ?? undefined, currentBranch.value?.branch)
    if (selectedCellId.value === slug) selectedCellId.value = null
    if (expandedCellId.value === slug) expandedCellId.value = null
    await fetchCells()
  }

  async function createLane(
    name: string,
    options: { switchTo?: boolean; from?: string } = {},
  ): Promise<string> {
    const from = options.from ?? currentBranch.value?.branch
    if (!from) throw new Error('No branch to fork from')
    const forked = await workspaceApi.forkBranch(name, from, currentFlow.value ?? undefined)
    if (options.switchTo) {
      await switchBranch(forked.branch)
    } else {
      await fetchBranches()
    }
    return forked.branch
  }

  async function rewindBranch(step: number) {
    const branch = currentBranch.value?.branch
    if (!branch) throw new Error('No branch to rewind')
    await workspaceApi.rewindBranch(branch, step, currentFlow.value ?? undefined)
    leaveMovedLane()
    await fetchBranches()
  }

  async function createPoint(name: string, step?: number) {
    const branch = currentBranch.value?.branch
    if (!branch) throw new Error('No branch to mark')
    await workspaceApi.checkpointBranch(branch, name, currentFlow.value ?? undefined, step)
    await fetchJournal()
  }

  async function runLane(): Promise<RanLane> {
    const result = await workspaceApi.runLane(
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    await fetchBranches()
    return result
  }

  async function stopSession(): Promise<CancelledRun> {
    const result = await workspaceApi.cancelRun(
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    await fetchBranches()
    return result
  }

  async function runCell(slug: string): Promise<RanCell> {
    const result = await workspaceApi.runCell(
      slug,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    await fetchCells()
    return result
  }

  function reset() {
    disconnectCascadeStream()
    isSidebarOpened.value = true
    viewMode.value = 'canvas'
    reactivity.value = 'auto'
    autoThresholdSeconds.value = 5
    branches.value = []
    agentSessions.value = []
    liveRuns.value = []
    setClaims([])
    agentCalls.value = {}
    currentFlow.value = null
    isBranchesLoading.value = false
    isSwitchingBranch.value = false
    isLaneForkPromptVisible.value = false
    cells.value = []
    isCellsLoading.value = false
    journal.value = []
    isJournalLoading.value = false
    selectedCellId.value = null
    expandedCellId.value = null
    uploadExperimentTarget.value = null
    uploadModelTarget.value = null
    experimentRemovals.value = {}
  }

  return {
    isSidebarOpened,
    toggleSidebar,
    viewMode,
    setViewMode,
    reactivity,
    setReactivity,
    autoThresholdSeconds,
    setAutoThresholdSeconds,
    fetchSettings,
    branches,
    currentFlow,
    setFlow,
    laneTree,
    currentBranch,
    currentBranchFamilyLine,
    currentHeadStep,
    currentBranchSteps,
    isBehindLaneHead,
    isLaneForkPromptVisible,
    ensureOnLaneHead,
    setLaneForkPromptVisible,
    currentBranchPoints,
    isBranchesLoading,
    isSwitchingBranch,
    fetchBranches,
    switchBranch,
    createLane,
    rewindBranch,
    createPoint,
    runLane,
    stopSession,
    reset,
    cells,
    notebookCells,
    isCellsLoading,
    fetchCells,
    renameCell,
    fetchCellSource,
    fetchCellLogs,
    copyCellContext,
    fetchAssetPreview,
    editCellSource,
    isLaneBehindHead,
    duplicateCell,
    addCellDownstream,
    createCell,
    deleteCell,
    runCell,
    journal,
    currentBranchActivities,
    isJournalLoading,
    fetchJournal,
    selectedCellId,
    selectCell,
    expandedCellId,
    setExpandedCellId,
    uploadExperimentTarget,
    setUploadExperimentTarget,
    publishExperiment,
    uploadModelTarget,
    setUploadModelTarget,
    publishModel,
    agentSessions,
    pairedAgent,
    pairedAgentLabel,
    endAgentSession,
    liveRuns,
    agentClaims,
    claimIdleMinutes,
    pairedAgents,
    cellLiveStates,
    isAnythingRunning,
    receiveLiveFrame,
    experimentRemovals,
  }
})
