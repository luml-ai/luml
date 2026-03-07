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
      @get-next-page="getNextPage"
      @sort="onSort"
    ></EvalsTable>
  </UiCard>
</template>

<script setup lang="ts">
import type { EvalsColumns, ModelScores } from '../../interfaces/interfaces'
import type { DatasetEmits, DatasetProps, FilterInterface, TableColumn } from './evals.interface'
import { computed, onBeforeMount, reactive, ref, watch } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { useDebounceFn } from '@vueuse/core'
import { Braces } from 'lucide-vue-next'
import UiCard from '../ui/UiCard.vue'
import EvalsTable from './EvalsTable.vue'
import EvalsScoresSingle from './scores/single/EvalsScoresSingle.vue'
import EvalsScoresMultiple from './scores/multiple/EvalsScoresMultiple.vue'

const emit = defineEmits<DatasetEmits>()

const evalsStore = useEvalsStore()

const props = defineProps<DatasetProps>()

const filter = reactive<FilterInterface>({
  search: '',
})

const averageScores = ref<ModelScores[] | null>(null)

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
  tree.push({
    title: 'feedback',
    children: ['AnnoName 1', 'Long AnnoName 2', 'AnnoName 3'],
  })
  tree.push({
    title: 'expectation',
    children: ['AnnoName 1 expectation', 'Long AnnoName 2 expectation', 'AnnoName 3 expectation'],
  })
  return tree
})

function onSort(sortParams: { sortField: string; sortOrder: 'asc' | 'desc' }) {
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
