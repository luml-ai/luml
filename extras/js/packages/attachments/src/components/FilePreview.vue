<template>
  <div class="preview-body">
    <PreviewStates v-if="previewState" :state="previewState" :error-message="error" />

    <template v-else>
      <SelectButton
        v-if="defaultView"
        v-model="view"
        :options="[defaultView, 'Raw']"
        :allow-empty="false"
        size="small"
        aria-label="Preview mode"
        class="view-toggle"
      />
      <CodePreview
        v-if="defaultView && view === 'Raw'"
        :text-content="textContent"
        :file-name="fileName"
      />
      <ImagePreview
        v-else-if="fileType === 'image'"
        :content-url="contentUrl"
        :file-name="fileName"
      />

      <SvgPreview v-else-if="fileType === 'svg'" :content-url="contentUrl" :file-name="fileName" />

      <MediaPreview
        v-else-if="fileType === 'audio' || fileType === 'video'"
        :type="fileType"
        :content-url="contentUrl"
      />

      <PdfPreview v-else-if="fileType === 'pdf'" :content-url="contentUrl" />

      <HtmlPreview v-else-if="fileType === 'html'" :content-url="contentUrl" />

      <TablePreview
        v-else-if="fileType === 'table'"
        :content-blob="contentBlob"
        :content-truncated="contentTruncated"
        :parquet-file="parquetFile"
        :total-rows="totalRows"
        :file-name="fileName"
      />

      <CodePreview
        v-else-if="fileType === 'text' || fileType === 'code'"
        :text-content="textContent"
        :file-name="fileName"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { SelectButton } from 'primevue'
import { getFileExtension } from '../utils/fileTypes'
import PreviewStates from './preview/PreviewStates.vue'
import ImagePreview from './preview/ImagePreview.vue'
import MediaPreview from './preview/MediaPreview.vue'
import PdfPreview from './preview/PdfPreview.vue'
import HtmlPreview from './preview/HtmlPreview.vue'
import TablePreview from './preview/TablePreview.vue'
import CodePreview from './preview/CodePreview.vue'
import SvgPreview from './preview/SvgPreview.vue'
import type { FilePreviewProps } from '../interfaces/interfaces'
import { useFilePreview } from '../hooks/useFilePreview'

const props = defineProps<FilePreviewProps>()
const {
  fileType,
  error,
  contentUrl,
  contentBlob,
  contentTruncated,
  textContent,
  parquetFile,
  previewState,
} = useFilePreview(props)

const defaultView = computed(() =>
  fileType.value === 'html'
    ? 'Rendered'
    : getFileExtension(props.fileName) === 'xml'
      ? 'Table'
      : undefined,
)
const view = ref<string>()
watch(
  () => [props.fileName, props.source],
  () => {
    view.value = defaultView.value
  },
  { immediate: true },
)

// A download reuses the previewed bytes only when they are the whole file.
defineExpose({
  contentBlob: computed(() => (contentTruncated.value ? undefined : contentBlob.value)),
})
</script>

<style scoped>
.view-toggle {
  align-self: flex-start;
  margin-bottom: 0.5rem;
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
