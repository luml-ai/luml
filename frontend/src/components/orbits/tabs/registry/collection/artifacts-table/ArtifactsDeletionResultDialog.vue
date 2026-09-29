<template>
  <Dialog
    :pt="ARTIFACTS_DELETION_RESULT_DIALOG_PT"
    :visible="visible"
    modal
    :draggable="false"
    @update:visible="onUpdateVisible"
  >
    <template #header>{{ title }}</template>
    <div class="artifacts-list">
      <div v-for="failure in failures" :key="failure.artifact_id" class="artifact">
        <div class="artifact-name">Artifact: {{ failure.name ?? failure.artifact_id }}</div>
        <div v-if="failure.reason === 'deployments'" class="reason">
          Used by deployments:
          <template v-for="(deployment, index) in failure.deployments" :key="deployment.id">
            <RouterLink
              :to="deploymentRoute(deployment.id)"
              target="_blank"
              rel="noopener noreferrer"
              class="link"
            >
              {{ deployment.name }}
            </RouterLink>
            ({{ deployment.status }})<span v-if="index < failure.deployments.length - 1">, </span
            ><span v-else>. Delete the deployments first.</span>
          </template>
        </div>
        <div v-else-if="failure.reason === 'tracks'" class="reason">
          Linked to tracks:
          <template v-for="(track, index) in failure.tracks" :key="track.id">
            <RouterLink
              :to="trackRoute(track.id)"
              target="_blank"
              rel="noopener noreferrer"
              class="link"
            >
              {{ track.name }}
            </RouterLink>
            <span v-if="index < failure.tracks.length - 1">, </span
            ><span v-else>. Unlink the artifact from the tracks first.</span>
          </template>
        </div>
        <div v-else-if="failure.reason === 'storage_error'" class="reason">
          The file could not be deleted from the bucket. Try again, or force delete to remove the
          artifact and leave the file in the bucket.
        </div>
        <div v-else class="reason">Could not be deleted. Try again.</div>
      </div>
    </div>
    <template #footer>
      <Button :disabled="loading" @click="close">Close</Button>
      <Button
        v-if="storageFailures.length"
        severity="warn"
        outlined
        :disabled="loading"
        @click="forceConfirmationVisible = true"
      >
        Force delete
      </Button>
    </template>
  </Dialog>
  <ForceDeleteConfirmDialog
    v-model:visible="forceConfirmationVisible"
    :title="forceDeleteTitle"
    :text="FORCE_DELETE_TEXT"
    :loading="loading"
    @confirm="forceDelete"
  />
</template>

<script setup lang="ts">
import type { ArtifactDeleteFailure } from '@/lib/api/artifacts/interfaces'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useArtifactsStore } from '@/stores/artifacts'
import { Button, Dialog, useToast } from 'primevue'
import { computed, ref } from 'vue'
import { RouterLink, useRoute, type RouteLocationRaw } from 'vue-router'
import ForceDeleteConfirmDialog from '@/components/ui/dialogs/ForceDeleteConfirmDialog.vue'
import { ARTIFACTS_DELETION_RESULT_DIALOG_PT } from './models-table.data'

const FORCE_DELETE_TEXT =
  'Force delete removes the artifact from the registry and leaves the file in the bucket. To force delete, type "delete" below.'

type Emits = {
  artifactsDeleted: [ids: string[]]
}

const emit = defineEmits<Emits>()
const artifactsStore = useArtifactsStore()
const route = useRoute()
const toast = useToast()

const loading = ref(false)
const forceConfirmationVisible = ref(false)

const failures = computed(() => artifactsStore.deletionResult?.failed ?? [])
const visible = computed(() => failures.value.length > 0)
const storageFailures = computed(() =>
  failures.value.filter((failure) => failure.reason === 'storage_error'),
)
const title = computed(() =>
  failures.value.length === 1 ? 'Artifact was not deleted' : 'Some artifacts were not deleted',
)
const forceDeleteTitle = computed(() =>
  storageFailures.value.length === 1
    ? 'Force delete this artifact?'
    : 'Force delete these artifacts?',
)

function deploymentRoute(deploymentId: string): RouteLocationRaw {
  return {
    name: 'orbit-deployments',
    params: {
      organizationId: route.params.organizationId,
      id: route.params.id,
    },
    query: { deployment: deploymentId },
  }
}

function trackRoute(trackId: string): RouteLocationRaw {
  return {
    name: 'track',
    params: {
      organizationId: route.params.organizationId,
      id: route.params.id,
      trackId,
    },
  }
}

function close(): void {
  artifactsStore.resetDeletionResult()
}

function onUpdateVisible(nextVisible: boolean): void {
  if (!nextVisible) close()
}

async function forceDelete(): Promise<void> {
  const resultBeforeForce = artifactsStore.deletionResult
  if (!resultBeforeForce || !storageFailures.value.length) return

  const failuresBeforeForce = [...resultBeforeForce.failed]
  const attemptedFailures = [...storageFailures.value]
  const attemptedIds = new Set(attemptedFailures.map(({ artifact_id }) => artifact_id))
  const names = new Map(
    attemptedFailures.map((failure) => [failure.artifact_id, failure.name ?? failure.artifact_id]),
  )

  loading.value = true
  try {
    const result = await artifactsStore.forceDeleteArtifacts([...attemptedIds])
    const notCompletedIds = new Set(result.notCompleted ?? [])
    const untouchedFailures = failuresBeforeForce.filter(
      ({ artifact_id }) => !attemptedIds.has(artifact_id),
    )
    const retryableFailures = attemptedFailures.filter(({ artifact_id }) =>
      notCompletedIds.has(artifact_id),
    )
    const mergedFailures: ArtifactDeleteFailure[] = [
      ...untouchedFailures,
      ...result.failed,
      ...retryableFailures,
    ]

    if (result.error) {
      toast.add(
        simpleErrorToast(deletionErrorMessage(result.error, result.deleted, result.notCompleted)),
      )
    } else if (result.deleted.length) {
      showSuccessToast(result.deleted, names)
    }

    if (mergedFailures.length) {
      artifactsStore.setDeletionResult({ ...result, failed: mergedFailures })
    } else {
      artifactsStore.resetDeletionResult()
    }

    if (result.deleted.length) emit('artifactsDeleted', result.deleted)
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to force delete artifacts')))
  } finally {
    loading.value = false
    forceConfirmationVisible.value = false
  }
}

function showSuccessToast(deleted: string[], names: Map<string, string>): void {
  const message =
    deleted.length === 1
      ? `Artifact "${names.get(deleted[0]) ?? deleted[0]}" deleted`
      : `${deleted.length} artifacts deleted`
  toast.add(simpleSuccessToast(message))
}

function deletionErrorMessage(
  error: unknown,
  deleted: string[],
  notCompleted: string[] | undefined,
): string {
  const message = getErrorMessage(error, 'Failed to force delete artifacts')
  if (!deleted.length) return message
  return `${message}. ${deleted.length} artifacts deleted, ${notCompleted?.length ?? 0} not completed`
}
</script>

<style scoped>
.artifacts-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.artifact-name {
  margin-bottom: 4px;
  color: var(--p-text-muted-color);
  font-size: 12px;
  font-weight: 500;
}

.reason {
  font-size: 14px;
  line-height: 1.5;
}
</style>
