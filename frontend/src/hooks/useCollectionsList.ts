import type {
  OrbitCollection,
  OrbitCollectionTypeEnum,
} from '@/lib/api/orbit-collections/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref, watch } from 'vue'
import { usePageLoading } from '@/hooks/usePageLoading'
import { useCollectionsStore } from '@/stores/collections'

interface RequestInfo {
  organizationId: string
  orbitId: string
}

export const useCollectionsList = (
  limit = 20,
  syncStore = true,
  types?: OrbitCollectionTypeEnum[],
) => {
  const collectionsStore = useCollectionsStore()

  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const { isLoading, invalidate, track } = usePageLoading()
  const searchQuery = ref<string>('')
  const typesQuery = ref<OrbitCollectionTypeEnum[]>(types ?? [])
  const tagsQuery = ref<string[]>([])

  const collectionsList = ref<OrbitCollection[]>([])

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    invalidate()
    await track(async (isCurrent) => {
      const response = await getCollectionsData(null)
      if (!isCurrent()) return
      addCollectionsToList(response.items)
      savedCursors.value.push(response.cursor)
    })
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    await track(async (isCurrent) => {
      const response = await getCollectionsData(cursor)
      if (!isCurrent()) return
      addCollectionsToList(response.items)
      savedCursors.value.push(response.cursor)
    })
  }

  async function getCollectionsData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    return await api.orbitCollections.getCollectionsList(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      { cursor, limit, search: searchQuery.value, types: typesQuery.value, tags: tagsQuery.value },
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  function reset() {
    invalidate()
    setCollectionsList([])
    savedCursors.value = []
    requestInfo.value = null
  }

  function addCollectionsToList(collections: OrbitCollection[]) {
    const existingCollectionsIds = collectionsList.value.map((collection) => collection.id)
    const newCollections = collections.filter(
      (collection) => !existingCollectionsIds.includes(collection.id),
    )
    setCollectionsList([...collectionsList.value, ...newCollections])
  }

  function setCollectionsList(collections: OrbitCollection[]) {
    if (syncStore) {
      collectionsStore.setCollectionsList(collections)
    } else {
      collectionsList.value = collections
    }
  }

  function setSearchQuery(query: string) {
    searchQuery.value = query
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    if (last >= collectionsList.value.length) {
      await getNextPage()
    }
  }

  function setTypesQuery(types: OrbitCollectionTypeEnum[]) {
    typesQuery.value = types
  }

  function setTagsQuery(tags: string[]) {
    tagsQuery.value = tags
  }

  if (syncStore) {
    watch(
      () => collectionsStore.collectionsList,
      (storeCollectionsList) => {
        collectionsList.value = storeCollectionsList
      },
      { immediate: true },
    )
  }

  return {
    setRequestInfo,
    getInitialPage,
    collectionsList,
    getNextPage,
    isLoading,
    pageIndex,
    reset,
    addCollectionsToList,
    searchQuery,
    setSearchQuery,
    onLazyLoad,
    typesQuery,
    setTypesQuery,
    tagsQuery,
    setTagsQuery,
  }
}
