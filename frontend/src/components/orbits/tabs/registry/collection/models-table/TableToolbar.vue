<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <div class="counter">{{ selectedModels.length }} Selected</div>
      <Button
        v-if="orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.delete)"
        variant="text"
        severity="secondary"
        v-tooltip="'Delete'"
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
        v-tooltip="'Settings'"
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
        v-tooltip="'Download'"
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
        @click="onDeployClick"
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
    <div class="toolbar-right">
      <MetricsSelect v-model="selectedMetrics" :metrics="metrics" />
    </div>
  </div>
  <CollectionModelEditor
    v-if="modelForEdit"
    :visible="!!modelForEdit"
    :data="modelForEdit"
    @update:visible="modelForEdit = null"
  ></CollectionModelEditor>
  <ForceDeleteConfirmDialog
    v-model:visible="isForceDeleting"
    :title="forceDeleteTitle"
    :text="FORCE_DELETE_TEXT"
    :loading="loading"
    @confirm="onForceDelete"
  ></ForceDeleteConfirmDialog>
  <DeploymentsCreateModal
    v-if="modelForDeployment"
    :visible="!!modelForDeployment"
    :initial-collection-id="collectionsStore.currentCollection?.id"
    :initial-model-id="modelForDeployment"
    @update:visible="onUpdateModelDeploymentVisible"
  ></DeploymentsCreateModal>
</template>

<script setup lang="ts">
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useOrbitsStore } from '@/stores/orbits'
import { Bolt, Download, Repeat, Rocket, Trash2 } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { MlModelStatusEnum, type MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { useModelsStore } from '@/stores/models'
import { Button, useConfirm, useToast } from 'primevue'
import { useRouter } from 'vue-router'
import { deleteModelConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useCollectionsStore } from '@/stores/collections'
import CollectionModelEditor from '../model/CollectionModelEditor.vue'
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import MetricsSelect from './MetricsSelect.vue'

const FORCE_DELETE_TEXT =
  'This action will permanently delete the models. If your bucket still contains the model files, the storage space will not be freed until you remove them manually. <br /> If you are sure, then write "delete" below'

type Props = {
  selectedModels: MlModel[]
  metrics: string[]
}

type Emits = {
  clearSelectedModels: []
}

const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const modelsStore = useModelsStore()
const router = useRouter()
const confirm = useConfirm()
const toast = useToast()

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const selectedMetrics = defineModel<string[] | null>('selectedMetrics')

const loading = ref(false)
const isForceDeleting = ref(false)
const modelForEdit = ref<MlModel | null>(null)
const modelForDeployment = ref<string | null>(null)

const downloadButtonDisabled = computed(() => !props.selectedModels.length)

const compareButtonDisabled = computed(() => {
  if (props.selectedModels.length < 2) return true
  const hasInvalidStatus = props.selectedModels.some(
    (model) => model.status !== MlModelStatusEnum.uploaded,
  )
  if (hasInvalidStatus) return true
  const hasAllExperimentSnapshots = props.selectedModels.every((selectedModel) => {
    const archiveName = FnnxService.findExperimentSnapshotArchiveName(selectedModel.file_index)
    return !!archiveName
  })
  return !hasAllExperimentSnapshots
})

const forceDeleteTitle = computed(() => {
  return props.selectedModels.length > 1 ? 'Force delete these models?' : 'Force delete this model?'
})

async function onDeleteClick() {
  if (!props.selectedModels.length || loading.value) return
  const hasFailedStatus = props.selectedModels.some(
    (model) => model.status !== MlModelStatusEnum.uploaded,
  )
  if (hasFailedStatus) {
    isForceDeleting.value = true
  } else {
    confirm.require(deleteModelConfirmOptions(confirmDelete, props.selectedModels.length))
  }
}

async function confirmDelete() {
  try {
    const modelsForDelete = props.selectedModels.map((model: any) => model.id) || []
    loading.value = true
    const result = await modelsStore.deleteModels(modelsForDelete)
    if (result.deleted?.length) {
      showSuccessDeleteToast(result.deleted)
    }
    if (result.failed?.length) {
      showErrorDeleteToast(result.failed)
    }
  } catch {
    toast.add(simpleErrorToast('Failed to delete models'))
  } finally {
    emits('clearSelectedModels')
    loading.value = false
  }
}

async function onForceDelete() {
  try {
    const modelsForDelete = props.selectedModels.map((model: any) => model.id) || []
    loading.value = true
    const result = await modelsStore.forceDeleteModels(modelsForDelete)
    if (result.deleted?.length) {
      showSuccessDeleteToast(result.deleted)
    }
    if (result.failed?.length) {
      showErrorDeleteToast(result.failed)
    }
  } catch {
    toast.add(simpleErrorToast('Failed to delete models'))
  } finally {
    emits('clearSelectedModels')
    loading.value = false
    isForceDeleting.value = false
  }
}

function showSuccessDeleteToast(models: string[]) {
  toast.add(
    simpleSuccessToast(`Models: ${models} has been removed from the collection successfully`),
  )
}

function showErrorDeleteToast(models: string[]) {
  toast.add(simpleErrorToast(`Failed to delete the models: ${models}`))
}

function openModelEditor() {
  if (!props.selectedModels.length) return
  modelForEdit.value = props.selectedModels[0]
}

function compareClick() {
  if (!props.selectedModels.length) return
  const selectedModelsIds = props.selectedModels.map((model) => model.id)
  router.push({ name: 'compare', query: { models: selectedModelsIds } })
}

async function downloadClick() {
  if (!props.selectedModels.length) throw new Error('Select model before')
  if (!props.selectedModels[0]?.id || loading.value) return
  loading.value = true
  try {
    const model = props.selectedModels[0]
    await modelsStore.downloadModel(model.id, model.file_name)
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load models'))
  } finally {
    emits('clearSelectedModels')
    loading.value = false
  }
}

function onDeployClick() {
  const modelId = props.selectedModels[0].id
  modelForDeployment.value = modelId
}

function onUpdateModelDeploymentVisible(val?: boolean) {
  if (val) return
  modelForDeployment.value = null
}
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 20px;
  margin-bottom: 10px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 500;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.counter {
  font-variant-numeric: tabular-nums;
}
</style>
