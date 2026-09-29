import type {
  OrbitCollection,
  OrbitCollectionCreator,
} from '@/lib/api/orbit-collections/interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'

export const useCollectionsStore = defineStore('collections', () => {
  const route = useRoute()

  const collectionsList = ref<OrbitCollection[]>([])
  const currentCollection = ref<OrbitCollection | null>(null)
  const creatorVisible = ref(false)
  const collectionsTags = ref<string[]>([])
  let currentCollectionRequest = 0

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string')
      throw new Error('Current organization not found')
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    return {
      organizationId: route.params.organizationId,
      orbitId: route.params.id,
    }
  })

  async function createCollection(
    payload: OrbitCollectionCreator,
    requestData?: typeof requestInfo.value,
  ) {
    const info = requestData ? requestData : requestInfo.value
    const collection = await api.orbitCollections.createCollection(
      info.organizationId,
      info.orbitId,
      payload,
    )
    setCollectionsList([collection, ...collectionsList.value])
    await getCollectionsTags()
  }

  async function updateCollection(collectionId: string, payload: OrbitCollectionCreator) {
    const updatedCollection = await api.orbitCollections.updateCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      collectionId,
      payload,
    )
    const newCollections = collectionsList.value.map((collection) => {
      return collection.id === collectionId ? updatedCollection : collection
    })
    setCollectionsList(newCollections)
    await getCollectionsTags()
  }

  async function deleteCollection(collectionId: string) {
    await api.orbitCollections.deleteCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      collectionId,
    )
    const newCollections = collectionsList.value.filter(
      (collection) => collection.id !== collectionId,
    )
    setCollectionsList(newCollections)
    await getCollectionsTags()
  }

  function setCollectionsList(collections: OrbitCollection[]) {
    collectionsList.value = collections
  }

  async function setCurrentCollection(collectionId: string) {
    const requestId = ++currentCollectionRequest
    const collection = await getCollection(collectionId)
    if (requestId === currentCollectionRequest) currentCollection.value = collection
  }

  function resetCurrentCollection() {
    currentCollectionRequest += 1
    currentCollection.value = null
  }

  function reset() {
    collectionsList.value = []
    currentCollection.value = null
    collectionsTags.value = []
  }

  function showCreator() {
    creatorVisible.value = true
  }

  function hideCreator() {
    creatorVisible.value = false
  }

  async function getCollection(collectionId: string) {
    return await api.orbitCollections.getCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      collectionId,
    )
  }

  async function getCollectionsTags() {
    const tags = await api.orbitCollections.getCollectionsTags(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
    )
    collectionsTags.value = tags
  }

  return {
    collectionsList,
    setCollectionsList,
    currentCollection,
    creatorVisible,
    requestInfo,
    createCollection,
    updateCollection,
    deleteCollection,
    reset,
    setCurrentCollection,
    resetCurrentCollection,
    showCreator,
    hideCreator,
    getCollection,
    getCollectionsTags,
    collectionsTags,
  }
})
