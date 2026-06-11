<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <div class="counter">{{ artifactLinksStore.selectedEntries.length }} Selected</div>
      <Button
        v-if="orbitsStore.getCurrentOrbitPermissions?.track.includes(PermissionEnum.delete)"
        variant="text"
        severity="secondary"
        v-tooltip="'Delete'"
        :disabled="!artifactLinksStore.selectedEntries.length"
        :loading="deleteLoading"
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
        :disabled="artifactLinksStore.selectedEntries.length !== 1"
        @click="openEditor"
      >
        <template #icon>
          <Bolt :size="14" />
        </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button, useConfirm, useToast } from 'primevue'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { Bolt, Trash2 } from 'lucide-vue-next'
import { deleteTrackEntryConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { ref } from 'vue'

const artifactLinksStore = useArtifactLinksStore()
const orbitsStore = useOrbitsStore()
const confirm = useConfirm()
const toast = useToast()

const deleteLoading = ref(false)

function onDeleteClick() {
  confirm.require(
    deleteTrackEntryConfirmOptions(deleteEntries, artifactLinksStore.selectedEntries.length),
  )
}

async function deleteEntries() {
  try {
    deleteLoading.value = true
    const trackId = artifactLinksStore.selectedEntries[0].track_id
    if (artifactLinksStore.selectedEntries.length > 1) {
      await artifactLinksStore.deleteEntries(
        trackId,
        artifactLinksStore.selectedEntries.map((e) => e.id),
      )
    } else {
      await artifactLinksStore.deleteEntry(trackId, artifactLinksStore.selectedEntries[0].id)
    }
    toast.add(simpleSuccessToast('Artifacts unlinked'))
    artifactLinksStore.clearSelectedEntries()
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to unlink artifacts')))
  } finally {
    deleteLoading.value = false
  }
}

function openEditor() {
  if (!artifactLinksStore.selectedEntries[0]) return
  artifactLinksStore.showEditor(artifactLinksStore.selectedEntries[0])
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
