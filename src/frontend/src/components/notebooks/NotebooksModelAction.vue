<template>
  <SplitButton severity="secondary" :model="EXPORT_ITEMS" @click="downloadFile()">
    <template #icon>
      <CloudDownload :size="14" />
    </template>
  </SplitButton>
  <ModelUpload
    v-if="modelBlob && !!organizationStore.currentOrganization"
    :model-blob="modelBlob"
    v-model:visible="modelUploadVisible"
    :file-name="file.name"
  ></ModelUpload>
</template>

<script setup lang="ts">
import type { LumlFile } from '@/lib/databases/database.interfaces'
import { SplitButton } from 'primevue'
import { CloudDownload } from 'lucide-vue-next'
import { DatabaseService } from '@/lib/databases/DatabaseService'
import { downloadFileFromBlob } from '@/helpers/helpers'
import { useOrganizationStore } from '@/stores/organization'
import ModelUpload from '../model-upload/ModelUpload.vue'
import { ref } from 'vue'

type Props = {
  file: LumlFile
}

const props = defineProps<Props>()
const organizationStore = useOrganizationStore()

const modelBlob = ref<Blob | null>(null)
const modelUploadVisible = ref(false)

const EXPORT_ITEMS = [
  {
    label: 'Upload to Registry',
    command: openModelUpload,
    disabled: () => !organizationStore.currentOrganization,
  },
  {
    label: 'Download model',
    command: downloadFile,
  },
]

async function downloadFile() {
  const blob = await DatabaseService.getFileBlob(props.file)
  downloadFileFromBlob(blob, props.file.name)
}

async function openModelUpload() {
  modelBlob.value = await DatabaseService.getFileBlob(props.file)
  modelUploadVisible.value = true
}
</script>

<style scoped></style>
