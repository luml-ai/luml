import type { BranchRecord } from '@/api/slices/workspace/workspace.interface'
import type { INotebookLane, INotebookLaneNode } from '@/components/notebooks/lanes/interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useToast } from 'primevue'
import { errorToast } from '@/toasts'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'

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

  const branches = ref<BranchRecord[]>([])
  const currentFlow = ref<string | null>(null)
  const isBranchesLoading = ref(false)
  const isSwitchingBranch = ref(false)

  const laneTree = computed(() => buildLaneTree(branches.value))
  const currentBranch = computed(() => branches.value.find((branch) => branch.checked_out) ?? null)

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

  function setViewMode(mode: 'canvas' | 'notebook') {
    viewMode.value = mode
  }

  function setFlow(flow: string | null) {
    if (currentFlow.value === flow) return
    currentFlow.value = flow
    void fetchBranches()
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

  async function createLane(name: string) {
    const from = currentBranch.value?.branch
    if (!from) throw new Error('No branch to fork from')
    await workspaceApi.forkBranch(name, from, currentFlow.value ?? undefined)
    await fetchBranches()
  }

  return {
    isSidebarOpened,
    toggleSidebar,
    viewMode,
    setViewMode,
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
  }
})
