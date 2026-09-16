import type {
  BranchRecord,
  CancelledRun,
  CellSummary,
  EvalResult,
  JournalTransaction,
  RanCell,
  RanLane,
} from '@/api/slices/workspace/workspace.interface'
import type { INotebookLane, INotebookLaneNode } from '@/components/notebooks/lanes/interface'
import type {
  NotebookAssetInterface,
  NotebookAssetType,
  PairableAgentInterface,
} from '@/components/notebooks/notebooks.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useToast } from 'primevue'
import { errorToast } from '@/toasts'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { FlowStream, streamToken } from '@/api/streams/flow'
import type { StreamFrame } from '@/api/streams/flow'

function formatStepCount(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}

function formatUpdatedAgo(ts: string | null): string {
  if (!ts) return ''
  const elapsedMinutes = Math.floor((Date.now() - new Date(ts).getTime()) / 60_000)
  if (elapsedMinutes < 1) return 'just now'
  if (elapsedMinutes < 60) return `${elapsedMinutes}m ago`
  const elapsedHours = Math.floor(elapsedMinutes / 60)
  if (elapsedHours < 24) return `${elapsedHours}h ago`
  return `${Math.floor(elapsedHours / 24)}d ago`
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

  const selectedCellId = ref<string | null>(null)
  const expandedCellId = ref<string | null>(null)

  const laneTree = computed(() => buildLaneTree(branches.value))
  const currentBranch = computed(() => branches.value.find((branch) => branch.checked_out) ?? null)
  const pairedAgentLabel = computed(() => currentBranch.value?.agent ?? null)
  const notebookCells = computed(() => cells.value.map(toNotebookCell))
  const currentBranchActivities = computed(() => {
    const branchId = currentBranch.value?.branch_id
    if (!branchId) return []
    return journal.value
      .filter((transaction) => transaction.branch === branchId)
      .sort((a, b) => b.step - a.step)
  })

  const currentBranchFamilyLine = computed(() => {
    const branch = currentBranch.value
    if (!branch) return ''
    if (branch.parent === null || branch.parent_step === null) return 'root lane'
    const headStep = branch.last_intent?.step ?? branch.forked_at_step
    return `started from ${branch.parent} · ${formatStepCount(headStep - branch.parent_step, 'step')} ago`
  })

  function toggleSidebar() {
    isSidebarOpened.value = !isSidebarOpened.value
  }

  function selectCell(id: string | null) {
    selectedCellId.value = id
  }

  function setExpandedCellId(id: string | null) {
    expandedCellId.value = id
  }

  async function pairAgent(agent: PairableAgentInterface) {
    const flow = currentFlow.value ?? undefined
    if (pairedAgentLabel.value) {
      await workspaceApi.unpairAgent(flow).catch(() => undefined)
    }
    await workspaceApi.pairAgent(agent.id, agent.name, flow)
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

  function scheduleCellsRefetch() {
    if (cascadeSettleTimer !== null) clearTimeout(cascadeSettleTimer)
    cascadeSettleTimer = setTimeout(() => {
      cascadeSettleTimer = null
      void fetchCells()
    }, 250)
  }

  function disconnectCascadeStream() {
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
        if (frame.type === 'lagged') return
        if (frame.flow !== opened.path) return
        if (frame.type === 'state') return
        scheduleCellsRefetch()
      })
      stream.connect()
      stream.watchJournal(opened.path, opened.flow_id)
    } catch (error) {
      toast.add(errorToast(error, 'Failed to open a live connection for cell updates'))
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

  async function fetchCellLogs(slug: string): Promise<string | null> {
    const detail = await workspaceApi.cellLogs(
      slug,
      currentFlow.value ?? undefined,
      currentBranch.value?.branch,
    )
    return detail.logs
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

  async function createLane(name: string) {
    const from = currentBranch.value?.branch
    if (!from) throw new Error('No branch to fork from')
    await workspaceApi.forkBranch(name, from, currentFlow.value ?? undefined)
    await fetchBranches()
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
    currentFlow.value = null
    isBranchesLoading.value = false
    isSwitchingBranch.value = false
    cells.value = []
    isCellsLoading.value = false
    journal.value = []
    isJournalLoading.value = false
    selectedCellId.value = null
    expandedCellId.value = null
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
    isBranchesLoading,
    isSwitchingBranch,
    fetchBranches,
    switchBranch,
    createLane,
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
    pairedAgentLabel,
    pairAgent,
  }
})
