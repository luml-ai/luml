import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { FLOW_FILE_EXTENSION } from '@/components/workspace/workspace.const'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type { WorkspaceFlow } from '@/api/slices/workspace/workspace.interface'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

const ITEM_TYPE_ORDER: Record<IWorkspaceFolderItem['type'], number> = {
  flow: 0,
  folder: 1,
  file: 2,
}

const MIN_LOADING_MS = 500

function joinPath(directory: string, segment: string): string {
  if (!directory) return segment
  return directory.endsWith('/') ? `${directory}${segment}` : `${directory}/${segment}`
}

function parentDirectory(directory: string): string | null {
  const trimmed = directory.replace(/\/+$/, '')
  const lastSlash = trimmed.lastIndexOf('/')
  if (lastSlash < 0) return null
  return lastSlash === 0 ? '/' : trimmed.slice(0, lastSlash)
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentDirectory = ref<string | null>(null)
  const flows = ref<WorkspaceFlow[]>([])
  const isDirectoryLoading = ref(false)

  const canGoUp = computed(() => {
    return currentDirectory.value !== null && parentDirectory(currentDirectory.value) !== null
  })

  async function fetchDirectory(directory?: string) {
    isDirectoryLoading.value = true
    const startedAt = Date.now()
    try {
      const listing = await workspaceApi.listFlows(directory)
      currentDirectory.value = listing.directory
      flows.value = listing.flows
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

  const items = computed<IWorkspaceFolderItem[]>(() => {
    const directory = currentDirectory.value ?? ''
    const flowItems: IWorkspaceFolderItem[] = []
    const folderNames = new Set<string>()

    for (const flow of flows.value) {
      const segments = flow.relative_path.split('/').filter(Boolean)
      const [firstSegment] = segments
      if (segments.length <= 1 && firstSegment) {
        flowItems.push({
          id: flow.path,
          name: firstSegment,
          type: 'flow',
          path: flow.path,
          size: 0,
        })
      } else if (firstSegment) {
        folderNames.add(firstSegment)
      }
    }

    const folderItems: IWorkspaceFolderItem[] = [...folderNames].map((name) => ({
      id: joinPath(directory, name),
      name,
      type: 'folder',
      path: joinPath(directory, name),
      size: 0,
    }))

    return [...flowItems, ...folderItems]
  })

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
