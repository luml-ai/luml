<template>
  <div>
    <div class="content">
      <div class="toolbar">
        <div class="counter">{{ selectedModels.length || 0 }} Selected</div>
        <Button
          v-if="orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.delete)"
          variant="text"
          severity="secondary"
          :disabled="!selectedModels.length"
          @click="onDeleteClick"
        >
          <template #icon>
            <Trash2 :size="14" />
          </template>
        </Button>
        <Button
          v-if="orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.update)"
          variant="text"
          severity="secondary"
          :disabled="selectedModels.length !== 1"
          @click="openModelEditor"
        >
          <template #icon>
            <Bolt :size="14" />
          </template>
        </Button>
        <Button
          variant="text"
          severity="secondary"
          :disabled="downloadButtonDisabled"
          @click="downloadClick"
        >
          <template #icon>
            <Download :size="14" />
          </template>
        </Button>
        <Button
          variant="text"
          severity="secondary"
          v-tooltip="'Deploy'"
          :disabled="selectedModels.length !== 1"
          @click="initDeploy"
        >
          <template #icon>
            <Rocket :size="14" />
          </template>
        </Button>
        <Button
          variant="text"
          severity="secondary"
          v-tooltip="'Compare'"
          :disabled="compareButtonDisabled"
          @click="compareClick"
        >
          <template #icon>
            <Repeat :size="14" />
          </template>
        </Button>
      </div>
      <div>
        <DataTable
          v-model:selection="selectedModels"
          :value="tableData"
          :pt="{
            emptyMessageCell: {
              style: 'padding: 25px 16px;',
            },
          }"
          selection-mode="multiple"
          data-key="id"
          style="font-size: 14px"
          class="table-white"
          scrollable
          scrollHeight="calc(100vh - 330px)"
          @row-click="onRowClick"
        >
          <template #empty>
            <div class="placeholder">No models to show. Add model to the table.</div>
          </template>
          <Column selectionMode="multiple"></Column>
          <Column field="model_name" header="Model name">
            <template #body="{ data }">
              <div v-tooltip="data.model_name" :style="columnBodyStyle + 'width: 180px'">
                {{ data.model_name }}
              </div>
              <div class="id-row">
                <span class="id-text">Id: </span>
                <UiId :id="data.id" class="id-value"></UiId>
              </div>
            </template>
          </Column>
          <Column field="created_at" header="Creation time">
            <template #body="{ data }">
              <div :style="columnBodyStyle + 'width: 180px'">
                {{ data.created_at }}
              </div>
            </template>
          </Column>
          <Column field="description" header="Description">
            <template #body="{ data }">
              <div v-tooltip="data.description" class="description" style="width: 203px">
                {{ data.description }}
              </div>
            </template></Column
          >
          <Column field="status" header="Status">
            <template #body="{ data }">
              <div style="width: 150px">
                <Tag
                  v-if="data.status === MlModelStatusEnum.deletion_failed"
                  severity="danger"
                  class="tag"
                  >Deletion failed</Tag
                >
                <Tag
                  v-if="data.status === MlModelStatusEnum.pending_deletion"
                  severity="warn"
                  class="tag"
                  >Pending deletions</Tag
                >
                <Tag
                  v-if="data.status === MlModelStatusEnum.pending_upload"
                  severity="warn"
                  class="tag"
                  >Pending upload</Tag
                >
                <Tag
                  v-if="data.status === MlModelStatusEnum.upload_failed"
                  severity="danger"
                  class="tag"
                  >Upload failed</Tag
                >
                <Tag
                  v-if="data.status === MlModelStatusEnum.uploaded"
                  severity="success"
                  class="tag"
                  >Uploaded</Tag
                >
              </div>
            </template>
          </Column>
          <Column field="tags" header="Tags">
            <template #body="{ data }">
              <div class="tags" style="width: 203px; overflow: hidden">
                <Tag v-for="(tag, index) in data.tags" :key="index" class="tag">{{ tag }}</Tag>
              </div>
            </template>
          </Column>
          <Column field="size" header="Size">
            <template #body="{ data }">
              <div :style="columnBodyStyle + 'width: 100px'">
                {{ data.size }}
              </div>
            </template>
          </Column>
          <Column
            v-for="key in metricsKeys"
            :key="key"
            :header="key"
            :field="'metrics.' + key"
            sortable
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
    <DeploymentsCreateModal
      v-if="modelForDeployment"
      :visible="!!modelForDeployment"
      :initial-collection-id="collectionsStore.currentCollection?.id"
      :initial-model-id="modelForDeployment"
      @update:visible="onUpdateModelDeploymentVisible"
    ></DeploymentsCreateModal>
    <CollectionModelEditor
      v-if="modelForEdit"
      :visible="!!modelForEdit"
      @update:visible="modelForEdit = null"
      :data="modelForEdit"
    ></CollectionModelEditor>
  </div>
</template>

<script setup lang="ts">
import { Button, useToast, Tag, useConfirm, type DataTableRowClickEvent } from 'primevue'
import { Trash2, Download, Rocket, Repeat, Bolt } from 'lucide-vue-next'
import { DataTable, Column } from 'primevue'
import { MlModelStatusEnum, type MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { computed, onBeforeMount, ref, watch } from 'vue'
import { useModelsStore } from '@/stores/models'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getSizeText } from '@/helpers/helpers'
import { deleteModelConfirmOptions } from '@/lib/primevue/data/confirm'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'
import { useRouter, useRoute } from 'vue-router'
import { useCollectionsStore } from '@/stores/collections'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import CollectionModelEditor from './model/CollectionModelEditor.vue'
import UiId from '@/components/ui/UiId.vue'

export interface SelectedModel
  extends Pick<
    MlModel,
    'id' | 'model_name' | 'file_name' | 'status' | 'description' | 'tags' | 'created_at' | 'metrics'
  > {
  size: string
}

const columnBodyStyle = 'white-space: nowrap; overflow:hidden; text-overflow: ellipsis;'

const modelsStore = useModelsStore()
const toast = useToast()
const confirm = useConfirm()
const orbitsStore = useOrbitsStore()
const router = useRouter()
const route = useRoute()
const collectionsStore = useCollectionsStore()

const selectedModels = ref<SelectedModel[]>([])
const loading = ref(false)
const modelForDeployment = ref<string | null>(null)
const modelForEdit = ref<SelectedModel | null>(null)

const tableData = computed<SelectedModel[]>(() => {
  return modelsStore.modelsList.map((item) => {
    return {
      id: item.id,
      model_name: item.model_name,
      file_name: item.file_name,
      created_at: new Date(item.created_at).toLocaleString(),
      description: item.description,
      tags: item.tags,
      size: getSizeText(item.size),
      status: item.status,
      metrics: item.metrics,
    }
  })
})

const metricsKeys = computed(() => {
  return tableData.value.reduce((acc: Set<string>, item) => {
    for (const key in item.metrics) {
      acc.add(key)
    }
    return acc
  }, new Set<string>())
})

const downloadButtonDisabled = computed(() => !selectedModels.value.length)

const compareButtonDisabled = computed(() => {
  if (selectedModels.value.length < 2) return true
  return selectedModels.value.some((model) => model.status !== MlModelStatusEnum.uploaded)
})

async function confirmDelete() {
  const modelsForDelete = selectedModels.value.map((model: any) => model.id) || []
  loading.value = true
  try {
    const result = await modelsStore.deleteModels(modelsForDelete)
    if (result.deleted?.length) {
      toast.add(
        simpleSuccessToast(
          `Models: ${result.deleted} has been removed from the collection successfully`,
        ),
      )
    }
    if (result.failed?.length) {
      toast.add(simpleErrorToast(`Failed to delete the models: ${result.failed}`))
    }
  } catch {
    toast.add(simpleErrorToast('Failed to delete models'))
  } finally {
    selectedModels.value = []
    loading.value = false
  }
}

async function onDeleteClick() {
  if (!selectedModels.value.length || loading.value) return
  confirm.require(deleteModelConfirmOptions(confirmDelete, selectedModels.value?.length))
}

async function downloadClick() {
  if (!selectedModels.value) throw new Error('Select model before')
  if (!selectedModels.value[0]?.id || loading.value) return
  loading.value = true
  try {
    const model = selectedModels.value[0]
    await modelsStore.downloadModel(model.id, model.file_name)
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load models'))
  } finally {
    selectedModels.value = []
    loading.value = false
  }
}

function onRowClick(event: DataTableRowClickEvent) {
  const target: any = event.originalEvent.target
  const modelId = event.data.id
  const isModelUploaded = event.data.status === MlModelStatusEnum.uploaded
  if (!target || !modelId || !isModelUploaded) return
  const rowIncludeCheckbox = !!target.querySelector('input[type="checkbox"]')
  if (rowIncludeCheckbox) return
  router.push({ name: 'model', params: { modelId } })
}

function compareClick() {
  if (!selectedModels.value.length) return
  const selectedModelsIds = selectedModels.value.map((model) => model.id)
  router.push({ name: 'compare', query: { models: selectedModelsIds } })
}

function initDeploy() {
  const modelId = selectedModels.value[0].id
  modelForDeployment.value = modelId
}

function onUpdateModelDeploymentVisible(val?: boolean) {
  if (val) return
  modelForDeployment.value = null
}

function openModelEditor() {
  if (!selectedModels.value[0]) return
  modelForEdit.value = selectedModels.value[0]
}

watch(tableData, (data) => {
  if (!selectedModels.value.length) return
  selectedModels.value = selectedModels.value
    .map((model) => data.find((updatedModel) => model.id === updatedModel.id))
    .filter((model) => !!model)
})

onBeforeMount(async () => {
  try {
    const modelsList = await modelsStore.getModelsList(
      String(route.params.organizationId),
      String(route.params.id),
      String(collectionsStore.currentCollection?.id),
    )
    modelsStore.setModelsList(modelsList)
  } catch {
    toast.add(simpleErrorToast('Failed to load models'))
  }
})
</script>

<style scoped>
.content {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 500;
  margin-bottom: 10px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.tag {
  font-weight: 400;
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

.counter {
  font-variant-numeric: tabular-nums;
}

.id-row {
  font-size: 12px;
}

.id-text {
  color: var(--p-text-muted-color);
}

@media (min-width: 768px) {
  .content {
    margin: 0 -88px;
  }
}
</style>
