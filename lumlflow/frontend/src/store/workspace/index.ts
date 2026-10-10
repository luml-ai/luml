import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { FLOW_FILE_EXTENSION } from '@/components/workspace/workspace.const'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type {
  OpenFlow,
  OpenFlowsTotals,
  WorkspaceFlow,
  WorkspaceFolder,
} from '@/api/slices/workspace/workspace.interface'
import { parentDirectory } from '@/helpers/path'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const ITEM_TYPE_ORDER: Record<IWorkspaceFolderItem['type'], number> = {
  flow: 0,
  folder: 1,
  file: 2,
}

const MIN_LOADING_MS = 500

export const OPEN_FLOWS_REFRESH_MS = 5_000

const NO_OPEN_FLOWS: OpenFlowsTotals = {
  open_flows: 0,
  running_kernels: 0,
  active_runs: 0,
  leased_sessions: 0,
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentDirectory = ref<string | null>(null)
  const flows = ref<WorkspaceFlow[]>([])
  const folders = ref<WorkspaceFolder[]>([])
  const isDirectoryLoading = ref(false)
  const openFlows = ref<OpenFlow[]>([])
  const openFlowsTotals = ref<OpenFlowsTotals>(NO_OPEN_FLOWS)
  let openFlowsRequest = 0

  const openFlowsByPath = computed(() => new Map(openFlows.value.map((flow) => [flow.path, flow])))
  // Open flows inside the listed directory but under one of its folders, keyed by the
  // folder's path as listed, so the key matches the row whatever the separator.
  const openFlowsByFolder = computed(() => {
    const folderPaths = new Map(folders.value.map((folder) => [folder.name, folder.path]))
    const grouped = new Map<string, OpenFlow[]>()
    for (const flow of openFlows.value) {
      const [folder, ...rest] = (flow.relative_path ?? '').split('/').filter(Boolean)
      const path = folder && folderPaths.get(folder)
      if (!flow.inside || !path || rest.length === 0) continue
      grouped.set(path, [...(grouped.get(path) ?? []), flow])
    }
    return grouped
  })

  // Polled, so a failure keeps the last answer rather than raising a toast.
  async function fetchOpenFlows() {
    const request = ++openFlowsRequest
    try {
      const listing = await workspaceApi.openFlows(currentDirectory.value ?? undefined)
      if (request !== openFlowsRequest) return
      openFlows.value = listing.flows
      openFlowsTotals.value = listing.totals
    } catch {}
  }

  const canGoUp = computed(() => {
    return currentDirectory.value !== null && parentDirectory(currentDirectory.value) !== null
  })

  function forgetOpenFlows() {
    openFlowsRequest++
    openFlows.value = []
    openFlowsTotals.value = NO_OPEN_FLOWS
  }

  async function fetchDirectory(directory?: string) {
    // Another directory's state must not linger over the loading skeletons.
    if (directory !== undefined && directory !== currentDirectory.value) forgetOpenFlows()
    isDirectoryLoading.value = true
    const startedAt = Date.now()
    try {
      const listing = await workspaceApi.listFlows(directory)
      if (listing.directory !== currentDirectory.value) forgetOpenFlows()
      currentDirectory.value = listing.directory
      flows.value = listing.flows
      folders.value = listing.folders
      // Every listing change (navigation, rename, delete, …) lands here.
      void fetchOpenFlows()
    } finally {
      const elapsed = Date.now() - startedAt
      if (elapsed < MIN_LOADING_MS) {
        await new Promise((resolve) => setTimeout(resolve, MIN_LOADING_MS - elapsed))
      }
      isDirectoryLoading.value = false
    }
  }

  function navigateToFolder(path: string) {
    return fetchDirectory(path)
  }

  function navigateUp() {
    if (currentDirectory.value === null) return Promise.resolve()
    const parent = parentDirectory(currentDirectory.value)
    return fetchDirectory(parent ?? undefined)
  }

  const items = computed<IWorkspaceFolderItem[]>(() => [
    ...flows.value.map((flow) => ({
      id: flow.path,
      name: flow.relative_path,
      type: 'flow' as const,
      path: flow.path,
      size: 0,
    })),
    ...folders.value.map((folder) => ({
      id: folder.path,
      name: folder.name,
      type: 'folder' as const,
      path: folder.path,
      size: 0,
    })),
  ])

  const sortedItems = computed(() => {
    return [...items.value].sort((a, b) => {
      const typeDiff = ITEM_TYPE_ORDER[a.type] - ITEM_TYPE_ORDER[b.type]
      if (typeDiff !== 0) return typeDiff
      return a.name.localeCompare(b.name)
    })
  })

  async function deleteFlow(path: string) {
    await workspaceApi.deleteFlow(path)
    await fetchDirectory(currentDirectory.value ?? undefined)
  }

  async function renameFlow(path: string, name: string) {
    await workspaceApi.renameFlow(path, name)
    await fetchDirectory(currentDirectory.value ?? undefined)
  }

  function buildDuplicateFlowName(name: string): string {
    const baseName = name.endsWith(FLOW_FILE_EXTENSION)
      ? name.slice(0, -FLOW_FILE_EXTENSION.length)
      : name
    const existingNames = new Set(
      sortedItems.value.filter((item) => item.type === 'flow').map((item) => item.name),
    )

    let candidate = `${baseName} (copy)${FLOW_FILE_EXTENSION}`
    let copyNumber = 2
    while (existingNames.has(candidate)) {
      candidate = `${baseName} (copy ${copyNumber})${FLOW_FILE_EXTENSION}`
      copyNumber++
    }
    return candidate
  }

  async function duplicateFlow(path: string) {
    const flow = flows.value.find((flow) => flow.path === path)
    if (!flow) return
    const name = buildDuplicateFlowName(flow.name)
    await workspaceApi.duplicateFlow(path, name)
    await fetchDirectory(currentDirectory.value ?? undefined)
  }

  async function createFlow(name: string) {
    const directory = currentDirectory.value ?? ''
    const created = await workspaceApi.createFlow(name, directory)
    try {
      await workspaceApi.checkoutFlow(created.path, `init flow ${created.flow}`)
    } catch {}
    await fetchDirectory(directory)
  }

  return {
    currentDirectory,
    isDirectoryLoading,
    canGoUp,
    openFlowsByPath,
    openFlows,
    openFlowsByFolder,
    openFlowsTotals,
    fetchOpenFlows,
    sortedItems,
    fetchDirectory,
    navigateToFolder,
    navigateUp,
    deleteFlow,
    renameFlow,
    duplicateFlow,
    createFlow,
  }
})
