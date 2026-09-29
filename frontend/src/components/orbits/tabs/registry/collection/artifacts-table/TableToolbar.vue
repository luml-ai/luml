<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <div class="counter">{{ selectedArtifacts.length }} Selected</div>
      <Button
        v-if="orbitsStore.getCurrentOrbitPermissions?.artifact.includes(PermissionEnum.delete)"
        variant="text"
        severity="secondary"
        aria-label="Delete"
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
        v-if="showDeployButton"
        variant="text"
        severity="secondary"
        v-tooltip="'Deploy'"
        :disabled="deployButtonDisabled"
        @click="onDeployClick"
      >
        <template #icon>
          <Rocket :size="14" />
        </template>
      </Button>
      <Button
        v-if="showCompareButton"
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
    v-model:visible="failedDeletionDialogVisible"
    :title="failedDeletionTitle"
    :text="FAILED_DELETION_TEXT"
    :loading="loading"
    secondary-action-label="Try again"
    @secondary-action="retryDelete"
    @confirm="onForceDelete"
  ></ForceDeleteConfirmDialog>
  <DeploymentsCreateModal
    v-if="modelForDeployment"
    :visible="!!modelForDeployment"
    :initial-collection-id="collectionsStore.currentCollection?.id"
    :initial-model-id="modelForDeployment"
    @update:visible="onUpdateModelDeploymentVisible"
  ></DeploymentsCreateModal>
  <ArtifactsDeletionResultDialog @artifacts-deleted="onResultArtifactsDeleted" />
</template>

<script setup lang="ts">
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useOrbitsStore } from '@/stores/orbits'
import { Bolt, Download, Repeat, Rocket, Trash2 } from 'lucide-vue-next'
import { computed, ref } from 'vue'
import { ArtifactStatusEnum, ArtifactTypeEnum, type Artifact } from '@/lib/api/artifacts/interfaces'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { useArtifactsStore } from '@/stores/artifacts'
import { Button, useConfirm, useToast } from 'primevue'
import { useRouter } from 'vue-router'
import { deleteArtifactConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useCollectionsStore } from '@/stores/collections'
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import ArtifactEditor from '../artifact/ArtifactEditor.vue'
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import MetricsSelect from './MetricsSelect.vue'
import ArtifactsDeletionResultDialog from './ArtifactsDeletionResultDialog.vue'

const FAILED_DELETION_TEXT =
  'The file could not be deleted from the bucket last time. Try again, or force delete to remove the artifact from the registry and leave the file in the bucket. To force delete, type "delete" below.'

type Props = {
  selectedArtifacts: Artifact[]
  metrics: string[]
}

type Emits = {
  clearSelectedArtifacts: []
  updateSelectedArtifacts: [artifacts: Artifact[]]
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
const failedDeletionDialogVisible = ref(false)
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

const failedDeletionTitle = computed(() => {
  return props.selectedArtifacts.length > 1 ? 'Delete these artifacts?' : 'Delete this artifact?'
})

const deployButtonDisabled = computed(() => {
  if (props.selectedArtifacts.length !== 1) return true
  const artifact = props.selectedArtifacts[0]
  const isUploaded = artifact.status === ArtifactStatusEnum.uploaded
  if (!isUploaded) return true
  const isModel = artifact.type === ArtifactTypeEnum.model
  if (isModel) return false
  return true
})

const showDeployButton = computed(() => {
  return (
    collectionsStore.currentCollection?.type === OrbitCollectionTypeEnum.model ||
    collectionsStore.currentCollection?.type === OrbitCollectionTypeEnum.mixed
  )
})

const showCompareButton = computed(() => {
  return collectionsStore.currentCollection?.type !== OrbitCollectionTypeEnum.dataset
})

function onDeleteClick(): void {
  if (!props.selectedArtifacts.length || loading.value) return
  const allDeletionsFailed = props.selectedArtifacts.every(
    (artifact) => artifact.status === ArtifactStatusEnum.deletion_failed,
  )
  if (allDeletionsFailed) {
    failedDeletionDialogVisible.value = true
  } else {
    confirm.require(deleteArtifactConfirmOptions(confirmDelete, props.selectedArtifacts.length))
  }
}

async function confirmDelete(): Promise<void> {
  await runDeletion(false)
}

async function retryDelete(): Promise<void> {
  failedDeletionDialogVisible.value = false
  await runDeletion(false)
}

async function onForceDelete(): Promise<void> {
  await runDeletion(true)
}

async function runDeletion(force: boolean): Promise<void> {
  const selectedArtifacts = [...props.selectedArtifacts]
  const artifactIds = selectedArtifacts.map(({ id }) => id)
  if (!artifactIds.length || loading.value) return

  loading.value = true
  artifactsStore.resetDeletionResult()
  try {
    const result = force
      ? await artifactsStore.forceDeleteArtifacts(artifactIds)
      : await artifactsStore.deleteArtifacts(artifactIds)
    artifactsStore.setDeletionResult(result.failed.length ? result : null)

    if (result.error) {
      retainNotCompletedSelection(selectedArtifacts, result.notCompleted ?? [])
      toast.add(
        simpleErrorToast(deletionErrorMessage(result.error, result.deleted, result.notCompleted)),
      )
      return
    }

    if (result.deleted.length) showSuccessDeleteToast(result.deleted, selectedArtifacts)
    emits('clearSelectedArtifacts')
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to delete artifacts')))
  } finally {
    loading.value = false
    failedDeletionDialogVisible.value = false
  }
}

function retainNotCompletedSelection(selectedArtifacts: Artifact[], notCompleted: string[]): void {
  const notCompletedIds = new Set(notCompleted)
  const storedArtifacts = new Map(
    artifactsStore.artifactsList.map((artifact) => [artifact.id, artifact]),
  )
  emits(
    'updateSelectedArtifacts',
    selectedArtifacts
      .filter(({ id }) => notCompletedIds.has(id))
      .map((artifact) => storedArtifacts.get(artifact.id) ?? artifact),
  )
}

function showSuccessDeleteToast(deletedIds: string[], selectedArtifacts: Artifact[]): void {
  const names = new Map(selectedArtifacts.map(({ id, name }) => [id, name]))
  const message =
    deletedIds.length === 1
      ? `Artifact "${names.get(deletedIds[0]) ?? deletedIds[0]}" deleted`
      : `${deletedIds.length} artifacts deleted`
  toast.add(simpleSuccessToast(message))
}

function deletionErrorMessage(
  error: unknown,
  deleted: string[],
  notCompleted: string[] | undefined,
): string {
  const message = getErrorMessage(error, 'Failed to delete artifacts')
  if (!deleted.length) return message
  return `${message}. ${deleted.length} artifacts deleted, ${notCompleted?.length ?? 0} not completed`
}

function onResultArtifactsDeleted(ids: string[]): void {
  if (modelForEdit.value && ids.includes(modelForEdit.value.id)) modelForEdit.value = null
}

function openModelEditor(): void {
  if (!props.selectedArtifacts.length) return
  modelForEdit.value = props.selectedArtifacts[0]
}

function compareClick(): void {
  if (!props.selectedArtifacts.length) return
  const selectedArtifactsIds = props.selectedArtifacts.map((artifact) => artifact.id)
  router.push({ name: 'compare', query: { artifacts: selectedArtifactsIds } })
}

async function downloadClick(): Promise<void> {
  if (!props.selectedArtifacts.length) throw new Error('Select artifact before')
  if (!props.selectedArtifacts[0]?.id || loading.value) return
  loading.value = true
  try {
    const artifact = props.selectedArtifacts[0]
    await artifactsStore.downloadArtifact(artifact.id, artifact.file_name)
  } catch {
    toast.add(simpleErrorToast('Failed to load artifacts'))
  } finally {
    emits('clearSelectedArtifacts')
    loading.value = false
  }
}

function onDeployClick(): void {
  const modelId = props.selectedArtifacts[0].id
  modelForDeployment.value = modelId
}

function onUpdateModelDeploymentVisible(val?: boolean): void {
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
