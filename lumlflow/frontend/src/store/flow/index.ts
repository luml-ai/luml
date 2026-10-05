import type {
  AssetPreview,
  BranchRecord,
  CancelledRun,
  CellSummary,
  EvalResult,
  JournalTransaction,
  RanCell,
  RanLane,
} from '@/api/slices/workspace/workspace.interface'
import type { AgentSessionRecord, PublishedAsset, PublishTarget } from '@/flow/api/types'
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
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { FlowStream, streamToken } from '@/api/streams/flow'
import type { AgentActivity, StreamFrame } from '@/api/streams/flow'

/** A run the daemon has announced and not yet seen end, by the cell it is of. */
export interface LiveRun {
  run_id: string
  slug: string
  /** Announced by the queue but not yet started by the kernel. */
  phase: 'queued' | 'running'
}

/**
 * What is happening to a cell right now, as opposed to what its stored state
 * says. A run beats an agent's call: when the agent asked for the run, the
 * kernel is what the card is waiting on.
 */
export type CellLiveState =
  | { kind: 'running'; run_id: string }
  | { kind: 'queued'; run_id: string }
  | { kind: 'agent'; actor: string; label: string; tool: string; inCall: boolean }

/**
 * How long a cell stays the agent's after its last call named it. The daemon
 * sees an agent only inside a call, and a call lasts milliseconds; the work —
 * reading the answer, deciding the next edit — happens between them. A cell
 * the agent touched is its until it touches another, leaves, or goes quiet
 * this long. The same idle window the workbench's task line uses.
 */
export const AGENT_FOCUS_MS = 90_000

/**
 * What an agent is doing, or just did. `inCall` says the daemon is inside the
 * call right now; afterwards `since` is when it answered, and the entry stands
 * until the agent moves on or the focus window closes.
 */
export interface AgentFocus extends AgentActivity {
  inCall: boolean
  since: number
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

  const isTerminalOpen = ref(false)
  const terminalHistory = ref<{ text: string; response?: string }[]>([])

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
  const uploadExperimentId = ref<string | null>(null)
  const uploadModelTarget = ref<{ slug: string; output: string } | null>(null)

  const laneTree = computed(() => buildLaneTree(branches.value))
  const currentBranch = computed(() => branches.value.find((branch) => branch.checked_out) ?? null)
  /**
   * Every registration on the flow, newest first. Read off `tree`, then kept
   * current by the daemon's `agents` frames — the lease is the daemon's memory,
   * and only it can say when a connection is gone.
   */
  const agentSessions = ref<AgentSessionRecord[]>([])
  /**
   * Paired means somebody is on the other end: a leased session. A row without
   * a lease was registered by hand for attribution, and nobody is behind it.
   */
  const pairedAgent = computed(() =>
    currentBranch.value?.checked_out
      ? (agentSessions.value.find((session) => session.leased) ?? null)
      : null,
  )
  const pairedAgentLabel = computed(() => pairedAgent.value?.label ?? null)
  /**
   * The runs in flight, as the daemon announces them. Not journaled, so this is
   * fed by the live frames alone and replaced whole by every catch-up.
   */
  const liveRuns = ref<LiveRun[]>([])
  /** One entry per leased agent: the call it is in, or the last one it made. */
  const agentFocus = ref<AgentFocus[]>([])
  // The clock the focus window is measured against. Ticks only while there is
  // a focus to expire, so an idle page runs no timer.
  const now = ref(Date.now())
  let focusClock: ReturnType<typeof setInterval> | null = null
  function keepClock() {
    const wanted = agentFocus.value.some((entry) => !entry.inCall)
    if (wanted && focusClock === null) {
      focusClock = setInterval(() => {
        now.value = Date.now()
      }, 5_000)
    } else if (!wanted && focusClock !== null) {
      clearInterval(focusClock)
      focusClock = null
    }
  }
  function setFocus(entries: AgentFocus[]) {
    agentFocus.value = entries
    now.value = Date.now()
    keepClock()
  }
  /** The agents still at work: in a call, or within the window after one. */
  const agentActivity = computed<AgentFocus[]>(() =>
    agentFocus.value.filter((entry) => entry.inCall || now.value - entry.since < AGENT_FOCUS_MS),
  )
  /** What the paired agent is doing this moment, if anything. */
  const currentActivity = computed<AgentFocus | null>(
    () => agentActivity.value[agentActivity.value.length - 1] ?? null,
  )
  const cellLiveStates = computed<Record<string, CellLiveState>>(() => {
    const states: Record<string, CellLiveState> = {}
    for (const activity of agentActivity.value) {
      if (!activity.slug) continue
      states[activity.slug] = {
        kind: 'agent',
        actor: activity.actor,
        label: activity.label,
        tool: activity.tool,
        inCall: activity.inCall,
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
  const notebookCells = computed(() => cells.value.map(toNotebookCell))
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

  function setUploadExperimentId(id: string | null) {
    uploadExperimentId.value = id
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

  /** Clear a registration nobody is behind. The daemon announces the new list. */
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
    setFocus([])
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

  /**
   * One journal frame for this flow. What moves the store is refetched after
   * a quiet moment; what is only live — a run's lifecycle, an agent mid-call —
   * is kept here, because nothing on the daemon answers "what is happening
   * right now" except these frames and the catch-up that opens them.
   */
  function receiveLiveFrame(frame: StreamFrame) {
    if (!('channel' in frame) || frame.channel !== 'journal') return
    if (frame.type === 'lagged' || frame.type === 'state') return
    if (frame.type === 'agents') {
      // The whole list at that moment, lease state included — replace it.
      // Nothing else in the tree moved, so no refetch is owed for it. An
      // agent whose lease is gone is not working on anything any more.
      agentSessions.value = frame.sessions
      const leased = new Set(
        frame.sessions.filter((session) => session.leased).map((session) => session.actor),
      )
      setFocus(agentFocus.value.filter((entry) => leased.has(entry.actor)))
      return
    }
    if (frame.type === 'activity') {
      const held = agentFocus.value.find((entry) => entry.actor === frame.actor)
      // Only a call's start puts an agent on a cell. The end of a call this
      // tab did not see begin — or dropped when the lane was moved under it —
      // is not a reason to mark one.
      if (frame.phase === 'ended' && !held) return
      const others = agentFocus.value.filter((entry) => entry.actor !== frame.actor)
      // A call that names no cell — `context`, `diff` — is the agent looking
      // around, and the cell it was on stays its; only a call naming another
      // cell moves it on.
      const slug = frame.slug ?? held?.slug ?? null
      setFocus([
        ...others,
        {
          actor: frame.actor,
          label: frame.label,
          tool: frame.tool,
          slug,
          inCall: frame.phase === 'started',
          since: Date.now(),
        },
      ])
      return
    }
    if (frame.type === 'caught_up') {
      liveRuns.value = frame.running.map((entry) => ({
        run_id: entry.run_id,
        slug: entry.slug,
        phase: 'running',
      }))
      // A tab that was away keeps nothing it inferred; what the daemon says
      // is in flight is the whole truth at that moment.
      setFocus(
        (frame.activity ?? []).map((entry) => ({ ...entry, inCall: true, since: Date.now() })),
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

  /** A rewind of the lane on screen, from this tab or any other. */
  function rewindsCurrentLane(ops: unknown[]): boolean {
    const branchId = currentBranch.value?.branch_id
    if (!branchId) return false
    return ops.some((op) => {
      const held = op as { op?: string; branch_id?: string }
      return held.op === 'rewound' && held.branch_id === branchId
    })
  }

  /**
   * The lane was moved to another step. Whatever cell an agent was on, it was
   * on it at the step the lane left: the card now shows that cell as it stood
   * at the step the lane went to, and nobody is working on that version. The
   * agent's next call puts it back on a cell — and a change it tries is
   * refused by the daemon until it has been told the lane moved.
   */
  function leaveMovedLane() {
    setFocus([])
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
      // The queue announces a run before the kernel starts it — that is the
      // moment a cell is "queued". A count that reached zero is the run being
      // left by everyone who waited on it.
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

  function toggleTerminal() {
    isTerminalOpen.value = !isTerminalOpen.value
  }

  async function evalScratch(code: string): Promise<EvalResult> {
    return workspaceApi.evalCode(code, currentFlow.value ?? undefined, currentBranch.value?.branch)
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

  async function fetchCellSource(slug: string): Promise<string> {
    const detail = await workspaceApi.cellSource(
      slug,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    return detail.source
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

  async function editCellSource(slug: string, source: string) {
    await workspaceApi.editCell(
      slug,
      source,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    await fetchCells()
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

  async function createLane(name: string, options: { switchTo?: boolean } = {}) {
    const from = currentBranch.value?.branch
    if (!from) throw new Error('No branch to fork from')
    await workspaceApi.forkBranch(name, from, currentFlow.value ?? undefined)
    if (options.switchTo) {
      await switchBranch(name)
    } else {
      await fetchBranches()
    }
  }

  async function rewindBranch(step: number) {
    const branch = currentBranch.value?.branch
    if (!branch) throw new Error('No branch to rewind')
    await workspaceApi.rewindBranch(branch, step, currentFlow.value ?? undefined)
    leaveMovedLane()
    await fetchBranches()
  }

  async function createPoint(name: string) {
    const branch = currentBranch.value?.branch
    if (!branch) throw new Error('No branch to mark')
    await workspaceApi.checkpointBranch(branch, name, currentFlow.value ?? undefined)
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
    isTerminalOpen.value = false
    terminalHistory.value = []
    branches.value = []
    agentSessions.value = []
    liveRuns.value = []
    setFocus([])
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
    uploadExperimentId.value = null
    uploadModelTarget.value = null
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
    isTerminalOpen,
    toggleTerminal,
    terminalHistory,
    evalScratch,
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
    uploadExperimentId,
    setUploadExperimentId,
    uploadModelTarget,
    setUploadModelTarget,
    publishModel,
    agentSessions,
    pairedAgent,
    pairedAgentLabel,
    endAgentSession,
    liveRuns,
    agentActivity,
    currentActivity,
    cellLiveStates,
    isAnythingRunning,
    receiveLiveFrame,
  }
})
