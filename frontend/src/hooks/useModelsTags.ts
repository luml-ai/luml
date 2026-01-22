import { api } from '@/lib/api'
import { ref } from 'vue'

export const useModelsTags = () => {
  const tags = ref<string[]>([])

  async function loadTags(organizationId: string, orbitId: string, collectionId: string) {
    const collectionDetails = await api.orbitCollections.getCollection(
      organizationId,
      orbitId,
      collectionId,
    )
    tags.value = collectionDetails.models_tags
  }

  function getTagsByQuery(query: string) {
    return [query, ...tags.value.filter((tag) => tag.toLowerCase().includes(query.toLowerCase()))]
  }

  return { loadTags, getTagsByQuery }
}
