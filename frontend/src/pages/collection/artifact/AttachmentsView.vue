<template>
  <UiPageLoader v-if="artifactsStore.attachmentsStatus === 'loading' || loading" />
  <div v-else-if="artifactsStore.attachmentsStatus === 'error' || error" class="attachments-error">
    <p>{{ error ?? artifactsStore.attachmentsError }}</p>
    <Button label="Try again" severity="secondary" @click="retry" />
  </div>
  <ModelAttachments v-else-if="provider" :provider="provider" class="attachments" />
</template>

<script setup lang="ts">
import { ModelAttachments } from '@luml/attachments'
import { useArtifactsStore } from '@/stores/artifacts'
import { Button } from 'primevue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import { useTarAttachmentsProvider } from '@/hooks/useTarAttachmentsProvider'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { watch } from 'vue'

const artifactsStore = useArtifactsStore()
const { provider, loading, error, init } = useTarAttachmentsProvider()

async function initializeProvider() {
  const artifact = artifactsStore.currentArtifact
  const downloader = artifactsStore.attachmentsDownloader
  const attachmentsIndex = artifactsStore.attachmentsIndex
  if (!artifact || !downloader || !attachmentsIndex || provider.value) return

  try {
    await init({
      downloader,
      fileIndex: artifact.file_index,
      attachmentsIndex,
      findAttachmentsTarPath: FnnxService.findAttachmentsTarPath,
      findAttachmentsIndexPath: FnnxService.findAttachmentsIndexPath,
    })
  } catch {
    // the provider exposes the initialization error for an in-page retry
  }
}

watch(
  () => artifactsStore.attachmentsStatus,
  (status) => {
    if (status === 'available') void initializeProvider()
  },
  { immediate: true },
)

async function retry() {
  if (artifactsStore.currentArtifact) {
    await artifactsStore.loadCurrentArtifactAttachments(artifactsStore.currentArtifact)
  }
}
</script>

<style scoped>
.attachments {
  height: calc(100vh - 320px);
}

.attachments-error {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 12px;
}
</style>
