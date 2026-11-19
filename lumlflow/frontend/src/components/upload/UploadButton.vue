<template>
  <Button
    :label="props.artifactKind ? `Upload ${props.artifactKind} to LUML` : 'Upload to LUML'"
    :size="props.artifactKind ? 'small' : undefined"
    severity="secondary"
    @click="uploadClick"
    :loading="loading"
  >
    <template #icon>
      <CloudUploadIcon :size="14" />
    </template>
  </Button>
  <UploadModal v-model:visible="visible" v-bind="props" />
</template>

<script setup lang="ts">
import type { UploadModalProps } from './upload.interface'
import { Button, useToast } from 'primevue'
import { CloudUploadIcon } from 'lucide-vue-next'
import { ref } from 'vue'
import { useAuthStore } from '@/store/auth'
import { errorToast } from '@/toasts'
import UploadModal from './UploadModal.vue'

const props = defineProps<UploadModalProps>()

const authStore = useAuthStore()
const toast = useToast()

const visible = ref<boolean>(false)
const loading = ref<boolean>(false)

async function uploadClick() {
  loading.value = true
  try {
    visible.value = await authStore.ensureAuth()
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>
