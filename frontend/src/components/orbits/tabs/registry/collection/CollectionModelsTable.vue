<template>
  <div>
    <div class="content">
      <div class="toolbar">
        <div>{{ selectedModels?.length || 0 }} Selected</div>
        <Button
          v-if="orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.delete)"
          variant="text"
          severity="secondary"
          :disabled="!selectedModels?.length"
          rounded
          @click="onDeleteClick"
        >
          <template #icon>
            <Trash2 :size="14" />
          </template>
        </Button>
        <Button variant="text" severity="secondary" rounded :disabled="selectedModels.length !== 1" @click="downloadClick">
          <template #icon>
            <Download :size="14" />
          </template>
        </Button>
        <Button variant="text" severity="secondary" rounded v-tooltip="'Deploy'" @click="$router.push({ name: 'orbit-deployments' })">
          <template #icon>
            <Rocket :size="14" />
          </template>
        </Button>
      </div>
      <div class="table-wrapper">
        <DataTable
          v-model:selection="selectedModels"
          :value="tableData"
          :pt="{
            emptyMessageCell: {
              style: 'padding: 25px 16px;',
            },
          }"
          dataKey="id"
          style="font-size: 14px"
        >
          <template #empty>
            <div class="placeholder">No models to show. Add model to the table.</div>
          </template>
          <Column selectionMode="multiple"></Column>
          <Column field="modelName" header="Model name">
            <template #body="{ data }">
              <div v-tooltip="data.modelName" :style="columnBodyStyle + 'width: 180px'">
                {{ data.modelName }}
              </div>
            </template>
          </Column>
          <Column field="createdTime" header="Creation time">
            <template #body="{ data }">
              <div :style="columnBodyStyle + 'width: 180px'">
                {{ data.createdTime }}
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
                <Tag v-if="data.status === MlModelStatusEnum.deletion_failed" severity="danger" class="tag">Deletion failed</Tag>
                <Tag v-if="data.status === MlModelStatusEnum.pending_deletion" severity="warn" class="tag">Pending deletions</Tag>
                <Tag v-if="data.status === MlModelStatusEnum.pending_upload" severity="warn" class="tag">Pending upload</Tag>
                <Tag v-if="data.status === MlModelStatusEnum.upload_failed" severity="danger" class="tag">Upload failed</Tag>
                <Tag v-if="data.status === MlModelStatusEnum.uploaded" severity="success" class="tag">Uploaded</Tag>
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
  </div>
</template>

<script setup lang="ts">
import { Button, useToast, Tag, useConfirm } from 'primevue'
import { Trash2, Download, Rocket } from 'lucide-vue-next'
import { DataTable, Column } from 'primevue'
import { MlModelStatusEnum } from '@/lib/api/orbit-ml-models/interfaces'
import { computed, onBeforeMount, onUnmounted, ref } from 'vue'
import { useModelsStore } from '@/stores/models'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getSizeText } from '@/helpers/helpers'
import { deleteModelConfirmOptions } from '@/lib/primevue/data/confirm'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'

const columnBodyStyle = 'white-space: nowrap; overflow:hidden; text-overflow: ellipsis;'

const modelsStore = useModelsStore()
const toast = useToast()
const confirm = useConfirm()
const orbitsStore = useOrbitsStore()

const selectedModels = ref<{ id: number, modelName: string, fileName: string }[]>([])
const loading = ref(false)

const tableData = computed(() =>
  modelsStore.modelsList.map((item) => {
    return {
      id: item.id,
      modelName: item.model_name,
      fileName: item.file_name,
      createdTime: new Date(item.created_at).toLocaleString(),
      description: item.description,
      tags: item.tags,
      size: getSizeText(item.size),
      status: item.status,
      metrics: item.metrics,
    }
  }),
)

const metricsKeys = computed(() => {
  return tableData.value.reduce((acc: Set<string>, item) => {
    for (const key in item.metrics) {
      acc.add(key)
    }
    return acc
  }, new Set<string>())
})

async function confirmDelete() {
  const modelsForDelete = selectedModels.value.map((model: any) => model.id)
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
  if (!selectedModels.value?.length || loading.value) return
  confirm.require(deleteModelConfirmOptions(confirmDelete, selectedModels.value?.length))
}

async function downloadClick() {
  if (!selectedModels.value[0]?.id || loading.value) return
  loading.value = true;
  try {
    const model = selectedModels.value[0]
    await modelsStore.downloadModel(model.id, model.fileName)
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load models'))
  } finally {
    selectedModels.value = []
    loading.value = false
  }
}

onBeforeMount(async () => {
  try {
    await modelsStore.loadModelsList()
  } catch {
    toast.add(simpleErrorToast('Failed to load models'))
  }
})

onUnmounted(() => {
  modelsStore.resetList()
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

.table-wrapper {
  overflow: auto;
  max-height: calc(100vh - 330px);
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

@media (min-width: 768px) {
  .content {
    margin: 0 -88px;
  }
}
</style>
