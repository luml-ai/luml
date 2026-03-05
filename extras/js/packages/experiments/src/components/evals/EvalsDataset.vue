<template>
  <UiCard :title="datasetId">
    <EvalsScoresSingle
      v-if="averageScores?.length === 1"
      :scores="averageScores[0]?.scores || []"
    ></EvalsScoresSingle>
    <EvalsScoresMultiple
      v-else
      :models-scores="averageScores || []"
      :models-info="modelsInfo"
    ></EvalsScoresMultiple>
    <EvalsTable
      :columns-tree="columnsTree"
      :data="data"
      :models-info="modelsInfo"
      :table-height="tableHeight"
      @get-next-page="getNextPage"
    ></EvalsTable>
  </UiCard>
</template>

<script setup lang="ts">
import type { EvalsColumns, EvalsInfo, ModelScores, ModelsInfo } from '../../interfaces/interfaces'
import { computed, onBeforeMount, ref } from 'vue'
import { useEvalsStore } from '../../store/evals'
import UiCard from '../ui/UiCard.vue'
import EvalsTable, { type EvalsTableColumn } from './EvalsTable.vue'
import EvalsScoresSingle from './scores/single/EvalsScoresSingle.vue'
import EvalsScoresMultiple from './scores/multiple/EvalsScoresMultiple.vue'

type Props = {
  data: EvalsInfo[]
  modelsInfo: ModelsInfo
  tableHeight?: string
  columns: EvalsColumns
  datasetId: string
}

interface Emits {
  (e: 'get-next-page'): void
}

const emit = defineEmits<Emits>()

const evalsStore = useEvalsStore()

const props = withDefaults(defineProps<Props>(), {
  tableHeight: '400px',
})

const averageScores = ref<ModelScores[] | null>(null)

const columnsTree = computed(() => {
  const tree: EvalsTableColumn[] = [
    {
      title: 'id',
    },
  ]
  if (Object.keys(props.modelsInfo).length > 1) {
    tree.push({
      title: 'modelId',
    })
  }
  for (const column of Object.keys(props.columns)) {
    tree.push({
      title: column,
      children: props.columns[column as keyof EvalsColumns],
    })
  }
  return tree
})

function getNextPage() {
  emit('get-next-page')
}

onBeforeMount(async () => {
  averageScores.value = await evalsStore.getProvider.getDatasetAverageScores(props.datasetId)
})
</script>

<style scoped></style>
