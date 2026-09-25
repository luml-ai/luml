<template>
  <Button
    text
    size="small"
    severity="secondary"
    label="upload to LUML"
    :pt="LINK_PT"
    :loading="modal?.loading ?? false"
    @click.stop="open"
  >
    <template #icon><CloudUpload :size="14" /></template>
  </Button>
  <UploadModal
    v-if="armed"
    ref="modal"
    :publish="publish"
    :default-name="defaultName"
    hide-trigger
  />
</template>

<script setup lang="ts">
import { nextTick, ref, useTemplateRef } from 'vue'
import { Button } from 'primevue'
import { CloudUpload } from 'lucide-vue-next'
import UploadModal from '@/components/upload/UploadModal.vue'
import type { PublishModel } from '@/components/upload/upload.interface'

/**
 * Send a cell's model to LUML from where it was made — the counterpart of
 * `TrackerUploadLink` for a model that is on no tracker. The dialog is the
 * Experiments half's own; the host supplies `publish`, which packages the
 * stored value in the kernel and starts the upload job. Mounted on the first
 * click, not before: the dialog reads the auth store and the toast service,
 * which the flow surface otherwise never needs.
 */
defineProps<{ publish: PublishModel; defaultName?: string }>()

const LINK_PT = { root: { class: 'px-1.5 py-1 text-sm font-normal text-primary' } }

const armed = ref(false)
const modal = useTemplateRef<InstanceType<typeof UploadModal>>('modal')

async function open(): Promise<void> {
  armed.value = true
  await nextTick()
  await modal.value?.open()
}
</script>
