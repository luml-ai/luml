<template>
  <UiCard>
    <template #header-left>
      <h3 class="card__title">
        <Braces :size="20" color="var(--p-primary-color)" />
        {{ datasetId }}
      </h3>
    </template>
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
      v-model:search="filter.search"
      :columns-tree="columnsTree"
      :data="data"
      :models-info="modelsInfo"
      :annotations-summary="annotationsSummary || { feedback: [], expectations: [] }"
      :dataset-id="datasetId"
      @get-next-page="getNextPage"
      @sort="onSort"
    ></EvalsTable>
  </UiCard>
</template>

<script setup lang="ts">
import type { EvalsColumns, ModelScores } from '../../interfaces/interfaces'
import type {
  DatasetEmits,
  DatasetProps,
  FilterInterface,
  SortParams,
  TableColumn,
} from './evals.interface'
import { computed, onBeforeMount, reactive, ref, watch } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { useDebounceFn } from '@vueuse/core'
import { Braces } from 'lucide-vue-next'
import { useAnnotationsStore } from '@/store/annotations'
import UiCard from '../ui/UiCard.vue'
import EvalsTable from './EvalsTable.vue'
import EvalsScoresSingle from './scores/single/EvalsScoresSingle.vue'
import EvalsScoresMultiple from './scores/multiple/EvalsScoresMultiple.vue'

const emit = defineEmits<DatasetEmits>()

const evalsStore = useEvalsStore()

const annotationsStore = useAnnotationsStore()

const props = defineProps<DatasetProps>()

const filter = reactive<FilterInterface>({
  search: '',
})

const averageScores = ref<ModelScores[] | null>(null)

const annotationsSummary = computed(
  () => annotationsStore.evalsAnnotationsSummaryByDatasetId[props.datasetId],
)

const columnsTree = computed(() => {
  const tree: TableColumn[] = [
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
  const feedbackColumns = annotationsSummary.value?.feedback.map((item) => item.name) || []
  tree.push({
    title: `feedback (${feedbackColumns.length})`,
    children: feedbackColumns,
  })
  const expectationColumns = annotationsSummary.value?.expectations.map((item) => item.name) || []
  tree.push({
    title: `expectation (${expectationColumns.length})`,
    children: expectationColumns,
  })
  return tree
})

function onSort(sortParams: SortParams) {
  emit('sort', sortParams)
}

function getNextPage() {
  emit('get-next-page')
}

function onFilterChange() {
  emit('filter-change', filter)
}

const debouncedOnFilterChange = useDebounceFn(onFilterChange, 300)

onBeforeMount(async () => {
  averageScores.value = await evalsStore.getProvider.getDatasetAverageScores(props.datasetId)
})

watch(filter, debouncedOnFilterChange)
</script>

<style scoped>
.card__title {
  font-size: 20px;
  display: flex;
  align-items: center;
  gap: 4px;
}
</style>
