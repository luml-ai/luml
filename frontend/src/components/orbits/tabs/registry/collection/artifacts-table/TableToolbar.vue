<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <div class="counter">{{ selectedArtifacts.length }} Selected</div>
      <Button
        v-if="orbitsStore.getCurrentOrbitPermissions?.artifact.includes(PermissionEnum.delete)"
        variant="text"
        severity="secondary"
        v-tooltip="'Delete'"
        :disabled="!selectedArtifacts.length"
        @click="onDeleteClick"
      >
        <template #icon>
          <Trash2 :size="14" />
        </template>
      </Button>
      <Button
        v-if="orbitsStore.getCurrentOrbitPermissions?.artifact.includes(PermissionEnum.update)"
        variant="text"
        severity="secondary"
        v-tooltip="'Settings'"
        :disabled="selectedArtifacts.length !== 1"
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
        :disabled="selectedArtifacts.length !== 1"
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
  <ArtifactEditor
    v-if="modelForEdit"
    :visible="!!modelForEdit"
    :data="modelForEdit"
    @update:visible="modelForEdit = null"
  ></ArtifactEditor>
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
import { ArtifactStatusEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { useArtifactsStore } from '@/stores/artifacts'
import { Button, useConfirm, useToast } from 'primevue'
import { useRouter } from 'vue-router'
import { deleteArtifactConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useCollectionsStore } from '@/stores/collections'
import ArtifactEditor from '../artifact/ArtifactEditor.vue'
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import MetricsSelect from './MetricsSelect.vue'

const FORCE_DELETE_TEXT =
  'This action will permanently delete the models. If your bucket still contains the model files, the storage space will not be freed until you remove them manually. <br /> If you are sure, then write "delete" below'

type Props = {
  selectedArtifacts: Artifact[]
  metrics: string[]
}

type Emits = {
  clearSelectedArtifacts: []
}

const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const artifactsStore = useArtifactsStore()
const router = useRouter()
const confirm = useConfirm()
const toast = useToast()

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const selectedMetrics = defineModel<string[] | null>('selectedMetrics')

const loading = ref(false)
const isForceDeleting = ref(false)
const modelForEdit = ref<Artifact | null>(null)
const modelForDeployment = ref<string | null>(null)

const downloadButtonDisabled = computed(() => !props.selectedArtifacts.length)

const compareButtonDisabled = computed(() => {
  if (props.selectedArtifacts.length < 2) return true
  const hasInvalidStatus = props.selectedArtifacts.some(
    (artifact) => artifact.status !== ArtifactStatusEnum.uploaded,
  )
  if (hasInvalidStatus) return true
  const hasAllExperimentSnapshots = props.selectedArtifacts.every((selectedArtifact) => {
    const archiveName = FnnxService.findExperimentSnapshotArchiveName(selectedArtifact.file_index)
    return !!archiveName
  })
  return !hasAllExperimentSnapshots
})

const forceDeleteTitle = computed(() => {
  return props.selectedArtifacts.length > 1
    ? 'Force delete these artifacts?'
    : 'Force delete this artifact?'
})

async function onDeleteClick() {
  if (!props.selectedArtifacts.length || loading.value) return
  const hasFailedStatus = props.selectedArtifacts.some(
    (artifact) => artifact.status !== ArtifactStatusEnum.uploaded,
  )
  if (hasFailedStatus) {
    isForceDeleting.value = true
  } else {
    confirm.require(deleteArtifactConfirmOptions(confirmDelete, props.selectedArtifacts.length))
  }
}

async function confirmDelete() {
  try {
    const artifactsForDelete = props.selectedArtifacts.map((artifact: any) => artifact.id) || []
    loading.value = true
    const result = await artifactsStore.deleteArtifacts(artifactsForDelete)
    if (result.deleted?.length) {
      showSuccessDeleteToast(result.deleted)
    }
    if (result.failed?.length) {
      showErrorDeleteToast(result.failed)
    }
  } catch {
    toast.add(simpleErrorToast('Failed to delete artifacts'))
  } finally {
    emits('clearSelectedArtifacts')
    loading.value = false
  }
}

async function onForceDelete() {
  try {
    const artifactsForDelete = props.selectedArtifacts.map((artifact: any) => artifact.id) || []
    loading.value = true
    const result = await artifactsStore.forceDeleteArtifacts(artifactsForDelete)
    if (result.deleted?.length) {
      showSuccessDeleteToast(result.deleted)
    }
    if (result.failed?.length) {
      showErrorDeleteToast(result.failed)
    }
  } catch {
    toast.add(simpleErrorToast('Failed to delete artifacts'))
  } finally {
    emits('clearSelectedArtifacts')
    loading.value = false
    isForceDeleting.value = false
  }
}

function showSuccessDeleteToast(artifacts: string[]) {
  toast.add(
    simpleSuccessToast(`Artifacts: ${artifacts} has been removed from the collection successfully`),
  )
}

function showErrorDeleteToast(artifacts: string[]) {
  toast.add(simpleErrorToast(`Failed to delete the artifacts: ${artifacts}`))
}

function openModelEditor() {
  if (!props.selectedArtifacts.length) return
  modelForEdit.value = props.selectedArtifacts[0]
}

function compareClick() {
  if (!props.selectedArtifacts.length) return
  const selectedArtifactsIds = props.selectedArtifacts.map((artifact) => artifact.id)
  router.push({ name: 'compare', query: { artifacts: selectedArtifactsIds } })
}

async function downloadClick() {
  if (!props.selectedArtifacts.length) throw new Error('Select artifact before')
  if (!props.selectedArtifacts[0]?.id || loading.value) return
  loading.value = true
  try {
    const artifact = props.selectedArtifacts[0]
    await artifactsStore.downloadArtifact(artifact.id, artifact.file_name)
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load artifacts'))
  } finally {
    emits('clearSelectedArtifacts')
    loading.value = false
  }
}

function onDeployClick() {
  const modelId = props.selectedArtifacts[0].id
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
