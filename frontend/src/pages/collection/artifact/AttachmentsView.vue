<template>
  <UiPageLoader v-if="loading" />
  <ModelAttachments v-else-if="provider" :provider="provider" />
</template>
<script setup lang="ts">
import { ModelAttachments } from '@/modules/model-attachments'
import { onMounted } from 'vue'
import { useArtifactsStore } from '@/stores/artifacts'
import { useTarAttachmentsProvider } from '@/hooks/useTarAttachmentsProvider'
import { ModelDownloader } from '@/lib/bucket-service'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import { getErrorMessage } from '@/helpers/helpers'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const artifactsStore = useArtifactsStore()
const { provider, loading, init } = useTarAttachmentsProvider()
const toast = useToast()

onMounted(async () => {
  if (provider.value) return

  try {
    if (!artifactsStore.currentArtifact?.file_index) {
      throw new Error('Artifact or file index does not exist')
    }

    const url = await artifactsStore.getDownloadUrl(artifactsStore.currentArtifact.id)
    const downloader = new ModelDownloader(url)

    await init({
      downloader,
      fileIndex: artifactsStore.currentArtifact.file_index,
      findAttachmentsTarPath: FnnxService.findAttachmentsTarPath,
      findAttachmentsIndexPath: FnnxService.findAttachmentsIndexPath,
    })
  } catch (e) {
    const message = getErrorMessage(e, 'Failed to initialize attachments')
    toast.add(simpleErrorToast(message))
  }
})
</script>
<style scoped></style>
