<template>
  <p v-if="error" role="alert">{{ error }}</p>
  <ModelAttachments
    v-else-if="provider && !provider.isEmpty()"
    :provider="provider"
    class="attachments"
  />
  <p v-else-if="empty || provider" class="text-muted-color">This experiment has no attachments.</p>
  <Skeleton v-else height="16rem" />
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, shallowRef } from 'vue'
import { ModelAttachments, TarAttachmentsProvider, urlPreviewBytes } from '@luml/attachments'
import { Skeleton } from 'primevue'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import type { ArchiveFile } from '@/api/slices/workspace/workspace.interface'
import { getErrorMessage } from '@/helpers/errors'

const props = defineProps<{ path: string; files: ArchiveFile[] }>()
const provider = shallowRef<TarAttachmentsProvider>()
const error = ref('')
const empty = ref(false)
const controller = new AbortController()
onBeforeUnmount(() => controller.abort())

onMounted(async () => {
  const tar = props.files.find((entry) => entry.name === 'attachments.tar')
  const index = props.files.find((entry) => entry.name === 'attachments.index.json')
  if (!tar && !index) {
    empty.value = true
    return
  }
  try {
    if (!tar || !index) throw new Error('The attachment archive or its index is missing.')
    const options = { signal: controller.signal }
    const response = await fetch(await workspaceApi.fileUrl(props.path, index.name), options)
    if (!response.ok) throw new Error(`Could not read the attachment index (${response.status})`)
    const attachmentsIndex = await response.json()
    if (
      !attachmentsIndex ||
      typeof attachmentsIndex !== 'object' ||
      Array.isArray(attachmentsIndex) ||
      Object.values(attachmentsIndex).some(
        (range) =>
          !Array.isArray(range) ||
          range.length !== 2 ||
          !range.every((n) => Number.isSafeInteger(n) && n >= 0) ||
          range[0] + range[1] > tar.size,
      )
    )
      throw new Error('Invalid attachment index')
    // A signed URL expires after an hour: a later read asks for a fresh one.
    const tarUrl = () => workspaceApi.fileUrl(props.path, tar.name)
    const bytes = await urlPreviewBytes(tarUrl, tar.size, options)
    const attachments = new TarAttachmentsProvider({
      // The member endpoint starts at the first byte of the inner tar.
      fileIndex: { [tar.name]: [0, tar.size] },
      attachmentsIndex,
      findAttachmentsIndexPath: () => index.name,
      findAttachmentsTarPath: () => tar.name,
      previewWorkerUrl: `${import.meta.env.BASE_URL}attachment-preview-sw.js`,
      downloader: {
        readRange: bytes.slice,
        async getFileFromBucket<T>(entries: Record<string, [number, number]>, name: string) {
          const [start, size] = entries[name]!
          return (await bytes.slice(start, start + size)) as T
        },
      },
    })
    await attachments.init()
    provider.value = attachments
  } catch (failure) {
    if (!controller.signal.aborted) error.value = getErrorMessage(failure)
  }
})
</script>

<style scoped>
.attachments {
  height: calc(100vh - 260px);
}
</style>
