<template>
  <UiPageLoader v-if="loading" />
  <ModelAttachments v-else-if="provider" :provider="provider" />
</template>
<script setup lang="ts">
import type { MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import { ModelAttachments } from '@/modules/model-attachments'
import { onMounted } from 'vue'
import { useModelsStore } from '@/stores/models'
import { useTarAttachmentsProvider } from '@/hooks/useTarAttachmentsProvider'
import { ModelDownloader } from '@/lib/bucket-service'
import { FnnxService } from '@/lib/fnnx/FnnxService'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

interface Props {
  model?: MlModel
}

const props = defineProps<Props>()

const modelsStore = useModelsStore()
const { provider, loading, init } = useTarAttachmentsProvider()

onMounted(async () => {
  if (provider.value) return

  try {
    if (!props.model?.file_index) {
      throw new Error('Model or file index does not exist')
    }

    const url = await modelsStore.getDownloadUrl(props.model.id)
    const downloader = new ModelDownloader(url)

    await init({
      downloader,
      fileIndex: props.model.file_index,
      findAttachmentsTarPath: FnnxService.findAttachmentsTarPath,
      findAttachmentsIndexPath: FnnxService.findAttachmentsIndexPath,
    })
  } catch (e) {
    console.error('Failed to initialize attachments:', e)
  }
})
</script>
<style scoped></style>
