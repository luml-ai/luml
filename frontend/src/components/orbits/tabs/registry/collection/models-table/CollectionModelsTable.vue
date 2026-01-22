<template>
  <div>
    <div class="content">
      <TableToolbar
        :selected-metrics="visibleMetrics"
        :selected-models="selectedModels"
        :metrics="allMetricsKeys"
        @update:selected-metrics="(val) => updateSelectedMetrics(val)"
        @clear-selected-models="resetSelectedModels"
      ></TableToolbar>
      <div>
        <DataTable
          v-model:selection="selectedModels"
          :value="modelsList"
          :pt="TABLE_PT"
          selection-mode="multiple"
          data-key="id"
          class="table-white"
          scrollable
          scrollHeight="calc(100vh - 340px)"
          :loading="isFirstPageLoading"
          :virtualScrollerOptions="virtualScrollerOptions"
          @row-click="onRowClick"
          @sort="onSort"
        >
          <template #empty>
            <div v-if="!isLoading" class="placeholder">
              No models to show. Add model to the table.
            </div>
          </template>
          <Column selectionMode="multiple"></Column>
          <Column
            field="model_name"
            header="Model name"
            sortable
            :pt="{ columnHeaderContent: { style: 'width: 180px' } }"
          >
            <template #body="{ data }">
              <NameColumnBody
                :name="data.model_name"
                :id="data.id"
                :column-body-style="columnBodyStyle"
              />
            </template>
          </Column>
          <Column
            field="created_at"
            header="Creation time"
            sortable
            :pt="{ columnHeaderContent: { style: 'width: 180px' } }"
          >
            <template #body="{ data }">
              <div :style="columnBodyStyle + 'width: 180px'">
                {{ new Date(data.created_at).toLocaleString() }}
              </div>
            </template>
          </Column>
          <Column
            field="description"
            header="Description"
            sortable
            :pt="{ columnHeaderContent: { style: 'width: 203px' } }"
          >
            <template #body="{ data }">
              <div v-tooltip="data.description" class="description" style="width: 203px">
                {{ data.description }}
              </div>
            </template></Column
          >
          <Column
            field="status"
            header="Status"
            sortable
            :pt="{ columnHeaderContent: { style: 'width: 150px' } }"
          >
            <template #body="{ data }">
              <StatusColumnBody :status="data.status" />
            </template>
          </Column>
          <Column
            field="tags"
            header="Tags"
            :pt="{ columnHeaderContent: { style: 'width: 203px' } }"
          >
            <template #body="{ data }">
              <TagsList :tags="data.tags" />
            </template>
          </Column>
          <Column
            field="size"
            header="Size"
            sortable
            :pt="{ columnHeaderContent: { style: 'width: 100px' } }"
          >
            <template #body="{ data }">
              <div :style="columnBodyStyle + 'width: 100px'">
                {{ getSizeText(data.size) }}
              </div>
            </template>
          </Column>
          <Column
            v-for="key in visibleMetrics"
            :key="key"
            :header="key"
            :field="key"
            sortable
            :pt="{ columnHeaderContent: { style: 'width: 100px' } }"
          >
            <template #body="{ data }">
              <div
                v-tooltip="key in data.metrics ? '' + data.metrics[key] : null"
                class="metric-column"
                style="width: 100px"
              >
                {{ key in data.metrics ? data.metrics[key] : '-' }}
              </div>
            </template>
          </Column>
        </DataTable>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  useToast,
  type DataTableRowClickEvent,
  type DataTableSortEvent,
  type VirtualScrollerProps,
} from 'primevue'
import { DataTable, Column } from 'primevue'
import {
  MlModelStatusEnum,
  type GetModelsListParams,
  type MlModel,
} from '@/lib/api/orbit-ml-models/interfaces'
import { onBeforeMount, ref, watch } from 'vue'
import { useModelsStore } from '@/stores/models'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useRouter, useRoute } from 'vue-router'
import { useCollectionsStore } from '@/stores/collections'
import { columnBodyStyle, TABLE_PT } from './models-table.data'
import { useModelsList } from '@/hooks/useModelsList'
import { getErrorMessage, getSizeText } from '@/helpers/helpers'
import { useDebounceFn } from '@vueuse/core'
import TableToolbar from './TableToolbar.vue'
import TagsList from './TagsList.vue'
import NameColumnBody from './NameColumnBody.vue'
import StatusColumnBody from './StatusColumnBody.vue'

const INITIAL_VISIBLE_METRICS_COUNT = 20

const modelsStore = useModelsStore()
const toast = useToast()
const router = useRouter()
const route = useRoute()
const collectionsStore = useCollectionsStore()
const { setRequestInfo, getInitialPage, modelsList, reset, onLazyLoad, setSortData, isLoading } =
  useModelsList()

const selectedModels = ref<MlModel[]>([])
const isFirstPageLoading = ref(true)
const allMetricsKeys = ref<string[]>([])
const visibleMetrics = ref<string[]>([])

const virtualScrollerOptions = ref<VirtualScrollerProps>({
  lazy: true,
  onLazyLoad: onLazyLoad,
  itemSize: 62,
  scrollHeight: 'calc(100vh - 330px)',
})

function onRowClick(event: DataTableRowClickEvent) {
  const target: any = event.originalEvent.target
  const modelId = event.data.id
  const isModelUploaded = event.data.status === MlModelStatusEnum.uploaded
  if (!target || !modelId || !isModelUploaded) return
  const rowIncludeCheckbox = !!target.querySelector('input[type="checkbox"]')
  if (rowIncludeCheckbox) return
  router.push({ name: 'model', params: { modelId } })
}

function resetSelectedModels() {
  selectedModels.value = []
}

async function getMetricsKeys() {
  try {
    const metrics = await modelsStore.getModelsMetrics()
    allMetricsKeys.value = metrics
    visibleMetrics.value = allMetricsKeys.value.slice(0, INITIAL_VISIBLE_METRICS_COUNT)
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load metrics')))
  }
}

async function initList() {
  try {
    reset()
    resetSelectedModels()
    isFirstPageLoading.value = true
    await getMetricsKeys()
    setRequestInfo({
      organizationId: String(route.params.organizationId),
      orbitId: String(route.params.id),
      collectionId: String(collectionsStore.currentCollection?.id),
    })
    await getInitialPage()
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load models')))
  } finally {
    isFirstPageLoading.value = false
  }
}

const updateSelectedMetrics = useDebounceFn((metrics: string[] | undefined | null) => {
  if (!metrics) {
    visibleMetrics.value = []
    return
  }
  visibleMetrics.value = metrics
}, 500)

function onSort(event: DataTableSortEvent) {
  const sortData = {
    sort_by: event.sortField as GetModelsListParams['sort_by'],
    order: event.sortOrder === 1 ? 'asc' : ('desc' as GetModelsListParams['order']),
  }
  setSortData(sortData)
  initList()
}

watch(modelsList, (data) => {
  if (!selectedModels.value.length) return
  selectedModels.value = selectedModels.value
    .map((model) => data.find((updatedModel) => model.id === updatedModel.id))
    .filter((model) => !!model)
})

onBeforeMount(initList)
</script>

<style scoped>
.content {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  overflow: hidden;
}

.description {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.metric-column {
  overflow: hidden;
  text-overflow: ellipsis;
}

@media (min-width: 768px) {
  .content {
    margin: 0 -88px;
  }
}
</style>
