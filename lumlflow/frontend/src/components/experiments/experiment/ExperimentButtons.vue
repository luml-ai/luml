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
import { Button, useConfirm, useToast } from 'primevue'
import { Trash2, Bolt, Repeat, Filter } from 'lucide-vue-next'
import { computed } from 'vue'
import { deleteExperimentConfirmOptions } from '@/confirm/confirm'
import { useExperimentsStore } from '@/store/experiments'
import { errorToast } from '@/toasts'

const confirm = useConfirm()
const toast = useToast()
const experimentsStore = useExperimentsStore()

const deleteDisabled = computed(() => {
  return experimentsStore.selectedExperiments.length === 0
})

const settingsDisabled = computed(() => {
  return experimentsStore.selectedExperiments.length !== 1
})

function onDelete() {
  const ids = experimentsStore.selectedExperiments.map((experiment) => experiment.id)
  const isMultiple = ids.length > 1
  confirm.require(
    deleteExperimentConfirmOptions(() => {
      onDeleteConfirm(ids)
    }, isMultiple),
  )
}

async function onDeleteConfirm(ids: string[]) {
  try {
    await experimentsStore.deleteExperiments(ids)
  } catch (error) {
    toast.add(errorToast(error))
  }
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
