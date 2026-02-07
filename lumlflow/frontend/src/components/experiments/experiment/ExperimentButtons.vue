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
import { computed } from 'vue'
import { deleteExperimentConfirmOptions } from '@/confirm/confirm'
import { useExperimentsStore } from '@/store/experiments'

const confirm = useConfirm()
const experimentsStore = useExperimentsStore()

const deleteDisabled = computed(() => {
  return experimentsStore.selectedExperiments.length === 0
})

const settingsDisabled = computed(() => {
  return experimentsStore.selectedExperiments.length !== 1
})

function onDelete() {
  const ids = experimentsStore.selectedExperiments.map((experiment) => experiment.id)
  confirm.require(
    deleteExperimentConfirmOptions(() => {
      console.log('delete', ids)
      experimentsStore.deleteExperiments(ids)
    }, ids.length > 1),
  )
}

function onSettings() {
  const experiment = experimentsStore.selectedExperiments[0]
  if (!experiment) throw new Error('Experiment not found')
  experimentsStore.setEditableExperiment(experiment)
}

function onCompare() {
  console.log('compare')
}

function onFilter() {
  console.log('filter')
}
</script>

<style scoped></style>
