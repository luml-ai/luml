<template>
  <Button
    text
    size="small"
    severity="secondary"
    label="upload to LUML"
    :pt="LINK_PT"
    :loading="loading"
    @click.stop="open"
  >
    <template #icon><CloudUpload :size="14" /></template>
  </Button>
  <UploadModal v-if="armed" v-model:visible="visible" :experiment-id="experimentId" />
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { Button, useToast } from 'primevue'
import { CloudUpload } from 'lucide-vue-next'
import UploadModal from '@/components/upload/UploadModal.vue'
import { useAuthStore } from '@/store/auth'
import { errorToast } from '@/toasts'

/**
 * Upload a cell's tracker record to LUML from where it was made. The dialog
 * is the Experiments half's own, reached here without the detour through
 * that tab. It mounts on the first authenticated click, not before, and is
 * opened only after it mounts so its `visible` watcher fetches the organizations.
 */
defineProps<{ experimentId: string }>()

const LINK_PT = { root: { class: 'px-1.5 py-1 text-sm font-normal text-primary' } }

const authStore = useAuthStore()
const toast = useToast()

const armed = ref(false)
const visible = ref(false)
const loading = ref(false)

async function open(): Promise<void> {
  loading.value = true
  try {
    if (!(await authStore.ensureAuth())) return
    armed.value = true
    await nextTick()
    visible.value = true
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}
</script>
