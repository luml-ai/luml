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
  <UploadModal v-if="armed" ref="modal" :experiment-id="experimentId" hide-trigger />
</template>

<script setup lang="ts">
import { nextTick, ref, useTemplateRef } from 'vue'
import { Button } from 'primevue'
import { CloudUpload } from 'lucide-vue-next'
import UploadModal from '@/components/upload/UploadModal.vue'

/**
 * Upload a cell's tracker record to LUML from where it was made. The dialog
 * is the Experiments half's own, reached here without the detour through
 * that tab. It mounts on the first click and not before: it reads the auth
 * store and the toast service, which the flow surface otherwise never needs.
 */
defineProps<{ experimentId: string }>()

const LINK_PT = { root: { class: 'px-1.5 py-1 text-sm font-normal text-primary' } }

const armed = ref(false)
const modal = useTemplateRef<InstanceType<typeof UploadModal>>('modal')

async function open(): Promise<void> {
  armed.value = true
  await nextTick()
  await modal.value?.open()
}
</script>
