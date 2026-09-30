import type {
  GetArtifactsListParams,
  Artifact,
  ArtifactTypeEnum,
} from '@/lib/api/artifacts/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref, watch, type ComputedRef } from 'vue'
import { useArtifactsStore } from '@/stores/artifacts'
import { useDebounceFn } from '@vueuse/core'

interface RequestInfo {
  organizationId: string
  orbitId: string
  collectionIds: string[]
}

export const useArtifactsList = (
  limit = 20,
  syncStore = true,
  types?: ArtifactTypeEnum[],
  excludedArtifactIds?: ComputedRef<string[]>,
) => {
  const artifactsStore = useArtifactsStore()
  const abortController = ref<AbortController | null>(null)

  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const sortData = ref<Pick<GetArtifactsListParams, 'sort_by' | 'order'>>({
    sort_by: undefined,
    order: undefined,
  })
  const typesQuery = ref<ArtifactTypeEnum[]>(types ?? [])
  const excludedTracksQuery = ref<string[]>([])

  function setExcludedTracksQuery(tracks: string[]) {
    excludedTracksQuery.value = tracks
  }

  const searchQuery = ref<string | null>(null)

  function setSearchQuery(query: string) {
    searchQuery.value = query
  }

  const list = ref<Artifact[]>([])

  function isVisible(artifact: Artifact): boolean {
    return !excludedArtifactIds?.value?.includes(artifact.id)
  }

  const filteredList = computed(() => list.value.filter(isVisible))

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    isLoading.value = true
    try {
      const response = await getData(null)
      addItemsToList(response.items, true)
      savedCursors.value = [response.cursor]
      if (!response.items.some(isVisible)) await loadUntilVisible()
    } finally {
      isLoading.value = false
    }
  }

  async function getNextPage() {
    if (!getNextPageCursor()) return
    isLoading.value = true
    try {
      await loadUntilVisible()
    } finally {
      isLoading.value = false
    }
  }

  // Excluded artifacts are filtered on the client. A page made only of them
  // adds nothing visible, and the list cannot ask for more until it shows
  // something: keep loading until a page has a visible item or the list ends.
  async function loadUntilVisible() {
    let cursor = getNextPageCursor()
    while (cursor) {
      const response = await getData(cursor)
      addItemsToList(response.items)
      savedCursors.value.push(response.cursor)
      if (response.items.some(isVisible)) return
      cursor = response.cursor
    }
  }

  async function getData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    abortController.value?.abort()
    abortController.value = new AbortController()
    return await api.artifacts.getOrbitArtifacts(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      {
        cursor,
        limit,
        ...sortData.value,
        types: typesQuery.value,
        collection_ids: requestInfo.value.collectionIds,
        search: searchQuery.value,
        excluded_tracks: excludedTracksQuery.value,
      },
      abortController.value.signal,
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  const hasNextPage = computed(() => getNextPageCursor() !== null)

  function reset() {
    setList([])
    savedCursors.value = []
    requestInfo.value = null
  }

  function addItemsToList(artifacts: Artifact[], reset = false) {
    if (reset) {
      setList(artifacts)
    } else {
      const existingArtifactsIds = list.value.map((artifact) => artifact.id)
      const newArtifacts = artifacts.filter(
        (artifact) => !existingArtifactsIds.includes(artifact.id),
      )
      setList([...list.value, ...newArtifacts])
    }
  }

  function setSortData(data: Pick<GetArtifactsListParams, 'sort_by' | 'order'>) {
    sortData.value = data
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    if (last === filteredList.value.length) {
      await getNextPage()
    }
  }

  function setList(artifacts: Artifact[]) {
    if (syncStore) {
      artifactsStore.setArtifactsList(artifacts)
    } else {
      list.value = artifacts
    }
  }

  async function onSortDataChange() {
    setList([])
    savedCursors.value = []
    if (requestInfo.value) {
      await getInitialPage()
    }
  }

  const debouncedOnSortDataChange = useDebounceFn(onSortDataChange, 500)

  function setLoading(value: boolean) {
    isLoading.value = value
  }

  function setTypesQuery(types: ArtifactTypeEnum[]) {
    typesQuery.value = types
  }

  if (syncStore) {
    watch(
      () => artifactsStore.artifactsList,
      (storedList) => {
        list.value = storedList
      },
      { immediate: true },
    )
  }

  watch([sortData, typesQuery, searchQuery], debouncedOnSortDataChange)

  return {
    requestInfo,
    setRequestInfo,
    getInitialPage,
    list,
    getNextPage,
    hasNextPage,
    isLoading,
    pageIndex,
    reset,
    addItemsToList,
    setSortData,
    onLazyLoad,
    setLoading,
    setTypesQuery,
    typesQuery,
    setSearchQuery,
    setExcludedTracksQuery,
    filteredList,
  }
}
