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
    <Button severity="secondary" variant="text" disabled @click="onCompare">
      <template #icon>
        <Repeat :size="14" />
      </template>
    </Button>
    <Button severity="secondary" variant="text" disabled @click="onFilter">
      <template #icon>
        <Filter :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Button, useConfirm } from 'primevue'
import { Trash2, Bolt, Repeat, Filter } from 'lucide-vue-next'
import { useGroupsStore } from '@/store/groups'
import { computed } from 'vue'
import { deleteGroupConfirmOptions } from '@/confirm/confirm'

const groupsStore = useGroupsStore()
const confirm = useConfirm()

const deleteDisabled = computed(() => {
  return groupsStore.selectedGroups.length === 0
})

const settingsDisabled = computed(() => {
  return groupsStore.selectedGroups.length !== 1
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
  console.log('compare')
}

function onFilter() {
  console.log('filter')
}
</script>

<style scoped></style>
