<template>
  <div class="file-preview card">
    <FilePreviewHeader
      :file-name="fileName"
      :file-size="fileSize"
      :file-path="filePath"
      @copy-path="$emit('copyPath')"
      @download="$emit('download')"
    />

    <div class="preview-body">
      <PreviewStates v-if="previewState" :state="previewState" :error-message="errorMessage" />

      <ImagePreview
        v-else-if="fileType === 'image'"
        :content-url="contentUrl!"
        :file-name="fileName"
      />

      <SvgPreview v-else-if="fileType === 'svg'" :content-url="contentUrl!" :file-name="fileName" />

      <MediaPreview
        v-else-if="fileType === 'audio' || fileType === 'video'"
        :type="fileType"
        :content-url="contentUrl!"
      />

      <PdfPreview v-else-if="fileType === 'pdf'" :content-url="contentUrl!" />

      <HtmlPreview v-else-if="fileType === 'html'" :content-url="contentUrl!" />

      <TablePreview
        v-else-if="fileType === 'table'"
        :content-blob="contentBlob!"
        :file-name="fileName"
      />

      <CodePreview
        v-else-if="fileType === 'text' || fileType === 'code'"
        :text-content="textContent!"
        :file-name="fileName"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import FilePreviewHeader from './preview/FilePreviewHeader.vue'
import PreviewStates from './preview/PreviewStates.vue'
import ImagePreview from './preview/ImagePreview.vue'
import MediaPreview from './preview/MediaPreview.vue'
import PdfPreview from './preview/PdfPreview.vue'
import HtmlPreview from './preview/HtmlPreview.vue'
import TablePreview from './preview/TablePreview.vue'
import CodePreview from './preview/CodePreview.vue'
import SvgPreview from './preview/SvgPreview.vue'
import type { PreviewState } from '../interfaces/interfaces'
import type { FileType } from '../utils/fileTypes'

interface Props {
  fileName: string
  fileSize: number
  filePath: string
  fileType: FileType | null
  previewState: PreviewState
  errorMessage?: string
  contentUrl?: string | null
  textContent?: string | null
  contentBlob?: Blob | null
}

interface Emits {
  (e: 'copyPath'): void
  (e: 'download'): void
}

defineProps<Props>()
defineEmits<Emits>()
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
