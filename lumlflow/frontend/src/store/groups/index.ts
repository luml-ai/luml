import type { Group, UpdateGroupPayload } from './groups.interface'
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { MOCK_GROUPS } from './groups.mock'
import { useToast } from 'primevue'
import { successToast } from '@/toasts'

export const useGroupsStore = defineStore('groups', () => {
  const toast = useToast()

  const groups = ref<Group[]>(MOCK_GROUPS)
  const selectedGroups = ref<Group[]>([])
  const editableGroup = ref<Group | null>(null)

  function setSelectedGroups(groups: Group[]) {
    selectedGroups.value = groups
  }

  function setEditableGroup(group: Group | null) {
    editableGroup.value = group
  }

  async function deleteGroups(groupIds: string[]) {
    groups.value = groups.value.filter((group) => !groupIds.includes(group.id))
    setEditableGroup(null)
    setSelectedGroups([])
    const message =
      groupIds.length > 1
        ? `${groupIds.length} groups deleted successfully`
        : 'Group deleted successfully'
    toast.add(successToast(message))
  }

  async function updateGroup(groupId: string, payload: UpdateGroupPayload) {
    groups.value = groups.value.map((group) => {
      if (group.id !== groupId) return group
      return { ...group, ...payload }
    })
    setSelectedGroups([])
    setEditableGroup(null)
  }

  return {
    groups,
    selectedGroups,
    setSelectedGroups,
    editableGroup,
    setEditableGroup,
    deleteGroups,
    updateGroup,
  }
})
