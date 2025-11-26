<template>
  <div class="file-preview card">
    <FilePreviewHeader
      :file-name="fileName"
      :file-size="fileSize"
      :file-path="props.file?.path || ''"
      @copy-path="copyPath"
      @download="downloadCurrentFile"
    />

    <div class="preview-body">
      <PreviewStates
        v-if="previewState"
        :state="previewState"
        :error-message="error || undefined"
      />

      <ImagePreview
        v-else-if="fileType === 'image' && contentUrl"
        :content-url="contentUrl"
        :file-name="fileName"
      />

      <SvgPreview
        v-else-if="fileType === 'svg' && contentUrl"
        :content-url="contentUrl"
        :file-name="fileName"
      />

      <MediaPreview
        v-else-if="(fileType === 'audio' || fileType === 'video') && contentUrl"
        :type="fileType"
        :content-url="contentUrl"
      />

      <PdfPreview v-else-if="fileType === 'pdf' && contentUrl" :content-url="contentUrl" />

      <HtmlPreview v-else-if="fileType === 'html' && contentUrl" :content-url="contentUrl" />

      <TablePreview
        v-else-if="fileType === 'table' && contentBlob"
        :content-blob="contentBlob"
        :file-name="fileName"
      />

      <CodePreview
        v-else-if="(fileType === 'text' || fileType === 'code') && textContent"
        :text-content="textContent"
        :file-name="fileName"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue'
import { useModelsStore } from '@/stores/models'
import { useFilePreview } from '../../../../../../../hooks/useFilePreview'
import { getFileType } from './utils/fileTypes'

import FilePreviewHeader from './preview/FilePreviewHeader.vue'
import PreviewStates from './preview/PreviewStates.vue'
import ImagePreview from './preview/ImagePreview.vue'
import MediaPreview from './preview/MediaPreview.vue'
import PdfPreview from './preview/PdfPreview.vue'
import HtmlPreview from './preview/HtmlPreview.vue'
import TablePreview from './preview/TablePreview.vue'
import CodePreview from './preview/CodePreview.vue'
import SvgPreview from './preview/SvgPreview.vue'

import { useToast } from 'primevue'
import { simpleSuccessToast } from '@/lib/primevue/data/toasts'
import type { FileNode } from './attachments.interfaces'

const toast = useToast()

const props = defineProps<{
  file: FileNode | null
  fileIndex: Record<string, [number, number]>
  organizationId: string
  orbitId: string
  collectionId: string
  modelId: string
}>()

const modelsStore = useModelsStore()

const { error, contentUrl, textContent, contentBlob, downloadFile, previewState } = useFilePreview({
    file: toRef(() => props.file),
    fileIndex: toRef(() => props.fileIndex),
    modelId: toRef(() => props.modelId),
    getDownloadUrl: (modelId: string) => modelsStore.getDownloadUrl(modelId),
  })

const fileName = computed(() => props.file?.name || '')
const fileSize = computed(() => props.file?.size || 0)
const fileType = computed(() => (props.file ? getFileType(props.file.name) : null))

const copyPath = async () => {
  if (!props.file?.path) return
  await navigator.clipboard.writeText(props.file.path)
  toast.add(simpleSuccessToast('Path copied to clipboard'))
}

const downloadCurrentFile = () => {
  if (!props.file) return
  downloadFile(props.file.name)
}
</script>

<style scoped>
.file-preview {
  flex: 1;
  display: flex;
  flex-direction: column;
  border-radius: 6px;
  overflow: hidden;
}

.preview-body {
  flex: 1;
  overflow: auto;
  padding: 1rem;
  position: relative;
  display: flex;
  flex-direction: column;
}
</style>
