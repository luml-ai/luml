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
import type { ExperimentSnapshotStaticParams, ModelsInfo } from '../../interfaces/interfaces'
import UiCard from '../ui/UiCard.vue'
import UiScalable from '../ui/UiScalable.vue'
import { Button } from 'primevue'
import { Maximize2 } from 'lucide-vue-next'
import StaticParametersMultipleTable from './StaticParametersMultipleTable.vue'

type Props = {
  parametersList: ExperimentSnapshotStaticParams[]
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const scaled = ref(false)

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
    const modelsWithParams = Object.entries(props.modelsInfo).map((entries) => {
      const modelValue =
        props.parametersList.find((staticParams) => staticParams.modelId === +entries[0])?.[
          param
        ] || '-'
      return [entries[1].name, modelValue]
    })
    const row: Record<string, any> = Object.fromEntries(modelsWithParams)
    row['Parameters'] = param
    return row
  })
})
</script>

<style scoped></style>
