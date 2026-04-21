import type { GetGroupsParams } from '@/api/api.interface'
import type { DetailedGroup, Group, UpdateGroupPayload } from './groups.interface'
import { ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { useToast } from 'primevue'
import { errorToast, successToast } from '@/toasts'
import { usePagination } from '@/hooks/usePagination'
import { apiService } from '@/api/api.service'
import { useDebounceFn } from '@vueuse/core'

const DEFAULT_LIMIT = 20

export const useGroupsStore = defineStore('groups', () => {
  const toast = useToast()
  const { data, getInitialPage, getNextPage, setParams, onLazyLoad, getParams, isLoading } =
    usePagination<Group, GetGroupsParams>(apiService.getGroups)

  const selectedGroups = ref<Group[]>([])
  const editableGroup = ref<Group | null>(null)
  const queryParams = ref<Partial<GetGroupsParams>>({ limit: DEFAULT_LIMIT })
  const detailedGroup = ref<DetailedGroup | null>(null)

  function setSelectedGroups(groups: Group[]) {
    selectedGroups.value = groups
  }

  function setEditableGroup(group: Group | null) {
    editableGroup.value = group
  }

  async function deleteGroups(groupIds: string[]) {
    const promises = groupIds.map((groupId) => apiService.deleteGroup(groupId))
    const results = await Promise.allSettled(promises)
    const deletedGroupIds = results
      .filter((result) => result.status === 'fulfilled')
      .map((result) => result.value.id)
    setSelectedGroups([])
    setEditableGroup(null)
    toast.add(successToast(`${deletedGroupIds.length} groups deleted successfully`))
    await getInitialPage()
  }

  async function updateGroup(groupId: string, payload: UpdateGroupPayload) {
    await apiService.updateGroup(groupId, payload)
    await getInitialPage()
    setSelectedGroups([])
    setEditableGroup(null)
    toast.add(successToast('Group updated successfully'))
  }

  function setQueryParams(params: Partial<GetGroupsParams>) {
    queryParams.value = params
  }

  async function updatePaginationParams(params: typeof queryParams.value) {
    setParams({ ...getParams(), ...params })
    try {
      await getInitialPage()
    } catch (error) {
      toast.add(errorToast(error))
    }
  }

  function getGroupById(groupId: string) {
    return apiService.getGroupById(groupId)
  }

  function setDetailedGroup(group: DetailedGroup) {
    detailedGroup.value = group
  }

  function reset() {
    selectedGroups.value = []
    editableGroup.value = null
    detailedGroup.value = null
  }

  const debouncedUpdatePaginationParams = useDebounceFn(updatePaginationParams, 500)

  watch(queryParams, debouncedUpdatePaginationParams)

  return {
    selectedGroups,
    setSelectedGroups,
    editableGroup,
    setEditableGroup,
    deleteGroups,
    updateGroup,
    data,
    getInitialPage,
    getNextPage,
    setParams,
    onLazyLoad,
    queryParams,
    setQueryParams,
    isLoading,
    detailedGroup,
    setDetailedGroup,
    getGroupById,
    reset,
  }
})
