import type { OrbitCollection, OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref, watch } from 'vue'
import { useCollectionsStore } from '@/stores/collections'

interface RequestInfo {
  organizationId: string
  orbitId: string
}

export const useCollectionsList = (limit = 20, syncStore = true, types?: OrbitCollectionTypeEnum[]) => {
  const collectionsStore = useCollectionsStore()

  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const searchQuery = ref<string>('')

  const collectionsList = ref<OrbitCollection[]>([])

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    isLoading.value = true
    const cursor = null
    const response = await getCollectionsData(cursor)
    addCollectionsToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    isLoading.value = true
    const response = await getCollectionsData(cursor)
    addCollectionsToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getCollectionsData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    return await api.orbitCollections.getCollectionsList(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      { cursor, limit, search: searchQuery.value, types },
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  function reset() {
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
    if (last === pageIndex.value * limit) {
      await getNextPage()
    }
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
  }
}
