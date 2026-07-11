<template>
  <div class="flex items-center gap-1">
    <Button severity="secondary" variant="text" :disabled="deleteDisabled" @click="onDelete">
      <template #icon>
        <Trash2 :size="14" />
      </template>
    </Button>
    <Button severity="secondary" variant="text" :disabled="settingsDisabled" @click="onSettings">
      <template #icon>
        <Bolt :size="14" />
      </template>
    </Button>
    <Button severity="secondary" variant="text" :disabled="compareDisabled" @click="onCompare">
      <template #icon>
        <Repeat :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Button, useConfirm } from 'primevue'
import { Trash2, Bolt, Repeat } from 'lucide-vue-next'
import { useGroupsStore } from '@/store/groups'
import { computed } from 'vue'
import { deleteGroupConfirmOptions } from '@/confirm/confirm'
import { useRouter } from 'vue-router'
import { ROUTE_NAMES } from '@/router/router.const'

const groupsStore = useGroupsStore()
const confirm = useConfirm()
const router = useRouter()

const deleteDisabled = computed(() => {
  return groupsStore.selectedGroups.length === 0
})

const settingsDisabled = computed(() => {
  return groupsStore.selectedGroups.length !== 1
})

const compareDisabled = computed(() => {
  return groupsStore.selectedGroups.length < 2
})

function onDelete() {
  confirm.require(
    deleteGroupConfirmOptions(() => {
      groupsStore.deleteGroups(groupsStore.selectedGroups.map((group) => group.id))
    }, groupsStore.selectedGroups.length > 1),
  )
}

function onSettings() {
  const groupForEdit = groupsStore.selectedGroups[0]
  if (!groupForEdit) throw new Error('Group for edit not found')
  groupsStore.setEditableGroup(groupForEdit)
}

function onCompare() {
  const groupsIds = groupsStore.selectedGroups.map((group) => group.id)
  router.push({ name: ROUTE_NAMES.GROUPS_COMPARISON, query: { groupsIds } })
}
</script>

<style scoped></style>
