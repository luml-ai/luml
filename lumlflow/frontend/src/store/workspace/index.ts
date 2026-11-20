import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { FLOW_FILE_EXTENSION } from '@/components/workspace/workspace.const'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type {
  OpenFlow,
  OpenFlowsTotals,
  WorkspaceListing,
} from '@/api/slices/workspace/workspace.interface'
import { parentDirectory } from '@/helpers/path'
import { useLocalStorage } from '@vueuse/core'
import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'

export const OPEN_FLOWS_REFRESH_MS = 5_000

const NO_OPEN_FLOWS: OpenFlowsTotals = {
  open_flows: 0,
  running_kernels: 0,
  active_runs: 0,
  leased_sessions: 0,
}

export const useWorkspaceStore = defineStore('workspace', () => {
  const currentDirectory = ref<string | null>(null)
  const pages = shallowRef<WorkspaceListing[]>([])
  const flows = computed(() => pages.value.flatMap((page) => page.flows))
  const folders = computed(() => pages.value.flatMap((page) => page.folders))
  const files = computed(() => pages.value.flatMap((page) => page.files))
  const lastPage = computed(() => pages.value[pages.value.length - 1])
  const total = computed(() => lastPage.value?.total ?? 0)
  const nextOffset = computed(() => lastPage.value?.next_offset ?? null)
  const showHidden = useLocalStorage('lumlflow.workspace.showHidden', false, {
    listenToStorageChanges: false,
  })
  const isLoadingMore = ref(false)
  let listingRequest = 0
  let listingPending = false
  let requestedDirectory: string | undefined
  let requestedHidden = showHidden.value
  let requestedPages = 1
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

  async function readPages(
    directory: string | undefined,
    count: number,
    base: WorkspaceListing[] = [],
    hidden = showHidden.value,
  ) {
    const request = ++listingRequest
    requestedHidden = hidden
    requestedDirectory = directory
    requestedPages = count
    listingPending = true
    isDirectoryLoading.value = pages.value.length === 0
    isLoadingMore.value = !isDirectoryLoading.value && count > pages.value.length
    try {
      const refreshed = [...base]
      while (refreshed.length < count) {
        const last = refreshed[refreshed.length - 1]
        if (last && last.next_offset === null) break
        const page = await workspaceApi.listFlows(
          last?.directory ?? directory,
          hidden,
          last?.next_offset ?? 0,
        )
        if (request !== listingRequest) return
        refreshed.push(page)
      }
      const first = refreshed[0]!
      if (first.directory !== currentDirectory.value) forgetOpenFlows()
      currentDirectory.value = first.directory
      showHidden.value = hidden
      pages.value = refreshed
      void fetchOpenFlows()
    } catch (error) {
      if (request === listingRequest) throw error
    } finally {
      if (request === listingRequest) {
        listingPending = false
        isDirectoryLoading.value = false
        isLoadingMore.value = false
        requestedPages = Math.max(pages.value.length, 1)
      }
    }
  }

  function fetchDirectory(directory?: string) {
    if (directory !== undefined && directory === currentDirectory.value) {
      return readPages(directory, requestedPages)
    }
    return readPages(directory, 1)
  }

  function openListing(page: WorkspaceListing, hidden: boolean) {
    return readPages(page.directory, 1, [page], hidden)
  }

  function changingListing() {
    return (
      listingPending &&
      (requestedDirectory !== currentDirectory.value || requestedHidden !== showHidden.value)
    )
  }

  function refreshDirectory() {
    if (currentDirectory.value === null || changingListing()) return Promise.resolve()
    return readPages(currentDirectory.value, requestedPages)
  }

  function setShowHidden(value: boolean) {
    if (showHidden.value === value) return Promise.resolve()
    return readPages(currentDirectory.value ?? requestedDirectory, 1, [], value)
  }

  function loadMore() {
    if (
      currentDirectory.value === null ||
      nextOffset.value === null ||
      isLoadingMore.value ||
      changingListing()
    ) {
      return Promise.resolve()
    }
    // A concurrent refresh may have shifted the page boundary on disk.
    return readPages(
      currentDirectory.value,
      pages.value.length + 1,
      listingPending ? [] : pages.value,
    )
  }

  function navigateToFolder(path: string) {
    return fetchDirectory(path)
  }

  function navigateUp() {
    if (currentDirectory.value === null) return Promise.resolve()
    const parent = parentDirectory(currentDirectory.value)
    return fetchDirectory(parent ?? undefined)
  }

  // The daemon sorts each group case-insensitively before applying the page offset.
  const sortedItems = computed<IWorkspaceFolderItem[]>(() => [
    ...flows.value.map((flow) => ({
      id: flow.path,
      name: flow.name,
      entryName: flow.relative_path === '.' ? flow.name + FLOW_FILE_EXTENSION : flow.relative_path,
      type: 'flow' as const,
      path: flow.path,
      size: 0,
      is_symlink: flow.is_symlink,
    })),
    ...folders.value.map((folder) => ({
      ...folder,
      id: folder.path,
      type: 'folder' as const,
      size: 0,
    })),
    ...files.value.map((file) => ({
      ...file,
      id: file.path,
      type: 'file' as const,
    })),
  ])

  async function deleteFlow(path: string) {
    await workspaceApi.deleteFlow(path)
    await refreshDirectory()
  }

  async function renameFlow(path: string, name: string) {
    await workspaceApi.renameFlow(path, name)
    await refreshDirectory()
  }

  function buildDuplicateFlowName(name: string): string {
    const stem = name.endsWith(FLOW_FILE_EXTENSION)
      ? name.slice(0, -FLOW_FILE_EXTENSION.length)
      : name
    const existingNames = new Set(
      sortedItems.value.filter((item) => item.type === 'flow').map((item) => item.entryName),
    )

    let candidate = `${stem} (copy)${FLOW_FILE_EXTENSION}`
    let copyNumber = 2
    while (existingNames.has(candidate)) {
      candidate = `${stem} (copy ${copyNumber})${FLOW_FILE_EXTENSION}`
      copyNumber++
    }
    return candidate
  }

  async function duplicateFlow(path: string) {
    const flow = flows.value.find((flow) => flow.path === path)
    if (!flow) return
    const name = buildDuplicateFlowName(flow.name)
    await workspaceApi.duplicateFlow(path, name)
    await refreshDirectory()
  }

  async function createFlow(name: string) {
    const directory = currentDirectory.value ?? ''
    const created = await workspaceApi.createFlow(name, directory)
    try {
      await workspaceApi.checkoutFlow(created.path, `init flow ${created.flow}`)
    } catch {}
    await refreshDirectory()
  }

  return {
    currentDirectory,
    isNotebookListing: computed(() => flows.value.some((flow) => flow.relative_path === '.')),
    files,
    total,
    nextOffset,
    showHidden,
    setShowHidden,
    loadMore,
    refreshDirectory,
    isLoadingMore,
    isDirectoryLoading,
    canGoUp,
    openFlowsByPath,
    openFlows,
    openFlowsByFolder,
    openFlowsTotals,
    fetchOpenFlows,
    sortedItems,
    fetchDirectory,
    openListing,
    navigateToFolder,
    navigateUp,
    deleteFlow,
    renameFlow,
    duplicateFlow,
    createFlow,
  }
})
