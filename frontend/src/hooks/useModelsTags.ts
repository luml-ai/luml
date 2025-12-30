import { useModelsStore } from '@/stores/models'
import { computed } from 'vue'

export const useModelsTags = () => {
  const modelsStore = useModelsStore()

  const existingTags = computed<string[]>(() => {
    const tagsSet = modelsStore.modelsList.reduce((acc: Set<string>, item) => {
      item.tags?.map((tag) => {
        acc.add(tag)
      })
      return acc
    }, new Set<string>())
    return Array.from(tagsSet)
  })

  function getTagsByQuery(query: string) {
    return [
      query,
      ...existingTags.value.filter((tag) => tag.toLowerCase().includes(query.toLowerCase())),
    ]
  }

  return { getTagsByQuery }
}
