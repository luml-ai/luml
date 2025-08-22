<template>
  <UiCard title="Compare parameters">
    <template #header-right>
      <Button severity="secondary" variant="text" @click="scaled = true">
        <template #icon>
          <Maximize2 :size="14" />
        </template>
      </Button>
    </template>
    <UiScalable v-model="scaled" title="Compare parameters">
      <StaticParametersMultipleTable :data="tableData"></StaticParametersMultipleTable>
      <template #scaled>
        <StaticParametersMultipleTable :data="tableData"></StaticParametersMultipleTable>
      </template>
    </UiScalable>
  </UiCard>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import type { ExperimentSnapshotStaticParams } from '../../interfaces/interfaces'
import { useModelsStore } from '@/stores/models'
import UiCard from '../ui/UiCard.vue'
import UiScalable from '../ui/UiScalable.vue'
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import StaticParametersMultipleTable from './StaticParametersMultipleTable.vue'

type Props = {
  parametersList: ExperimentSnapshotStaticParams[]
  modelsIds: number[]
}

const props = defineProps<Props>()

const modelsStore = useModelsStore()

const scaled = ref(false)

const modelsWithNames = computed(() =>
  props.modelsIds.map((modelId) => {
    const model = modelsStore.modelsList.find((model) => model.id === modelId)
    return {
      id: modelId,
      name: model?.model_name || 'Unknown model',
    }
  }),
)

const uniqueParams = computed(() => {
  const paramsSet = props.parametersList.reduce((acc, item) => {
    const keys = Object.keys(item) as (keyof ExperimentSnapshotStaticParams)[]
    keys.map((key) => acc.add(key))
    return acc
  }, new Set<keyof ExperimentSnapshotStaticParams>())
  paramsSet.delete('modelId')
  return Array.from(paramsSet)
})

const tableData = computed(() => {
  return uniqueParams.value.map((param) => {
    const modelsWithParams = modelsWithNames.value.map((model) => {
      const modelValue =
        props.parametersList.find((staticParams) => staticParams.modelId === model.id)?.[param] ||
        '-'
      return [model.name, modelValue]
    })
    const row: Record<string, any> = Object.fromEntries(modelsWithParams)
    row['Parameters'] = param
    return row
  })
})
</script>

<style scoped></style>
