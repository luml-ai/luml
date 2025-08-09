import type {
  OrbitCollection,
  OrbitCollectionCreator,
} from '@/lib/api/orbit-collections/interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { dataforceApi } from '@/lib/api'
import { useRoute } from 'vue-router'

export const useCollectionsStore = defineStore('collections', () => {
  const route = useRoute()

  const collectionsList = ref<OrbitCollection[]>([])
  const currentCollection = ref<OrbitCollection | null>(null)

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string') throw new Error('Current organization not found')
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    return {
      organizationId: +route.params.organizationId,
      orbitId: +route.params.id,
    }
  })

  async function loadCollections(organizationId?: number, orbitId?: number) {
    collectionsList.value = await dataforceApi.orbitCollections.getCollectionsList(
      organizationId ?? requestInfo.value.organizationId,
      orbitId ?? requestInfo.value.orbitId,
    )
  }

  async function createCollection(payload: OrbitCollectionCreator, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const collection = await dataforceApi.orbitCollections.createCollection(
      info.organizationId,
      info.orbitId,
      payload,
    )
    collectionsList.value.push(collection)
  }

  async function updateCollection(collectionId: number, payload: OrbitCollectionCreator) {
    const updatedCollection = await dataforceApi.orbitCollections.updateCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      collectionId,
      payload,
    )
    collectionsList.value = collectionsList.value.map((collection) => {
      return collection.id === collectionId ? updatedCollection : collection
    })
  }

  async function deleteCollection(collectionId: number) {
    await dataforceApi.orbitCollections.deleteCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      collectionId,
    )
    collectionsList.value = collectionsList.value.filter(
      (collection) => collection.id !== collectionId,
    )
  }

  async function setCurrentCollection(collectionId: number) {
    currentCollection.value =
      collectionsList.value.find((collection) => collection.id === collectionId) || null
  }

  function resetCurrentCollection() {
    currentCollection.value = null
  }

  function reset() {
    collectionsList.value = []
    resetCurrentCollection()
  }

  return {
    collectionsList,
    currentCollection,
    loadCollections,
    createCollection,
    updateCollection,
    deleteCollection,
    reset,
    setCurrentCollection,
    resetCurrentCollection,
  }
})
