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
  <UploadModal
    v-if="armed"
    v-model:visible="visible"
    :publish="publish"
    :default-name="defaultName"
  />
</template>

<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { Button, useToast } from 'primevue'
import { CloudUpload } from 'lucide-vue-next'
import UploadModal from '@/components/upload/UploadModal.vue'
import { useAuthStore } from '@/store/auth'
import { errorToast } from '@/toasts'
import type { PublishModel } from '@/components/upload/upload.interface'

/**
 * Send a cell's model to LUML from where it was made — the counterpart of
 * `TrackerUploadLink` for a model that is on no tracker. The dialog is the
 * Experiments half's own; the host supplies `publish`, which packages the
 * stored value in the kernel and starts the upload job. The dialog mounts on
 * the first authenticated click, not before, and is opened only after it
 * mounts so its `visible` watcher fetches the organizations.
 */
defineProps<{ publish: PublishModel; defaultName?: string }>()

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
