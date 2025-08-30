<template>
  <Dialog v-model:visible="visible" :draggable="false" :pt="dialogPt" position="right">
    <TracesInputs :models-info="modelsInfo"></TracesInputs>
    <TracesModels :models-info="modelsInfo" class="models"></TracesModels>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import { Dialog } from 'primevue'
import TracesInputs from './inputs/TracesInputs.vue'
import TracesModels from './models/TracesModels.vue'
import type { ModelsInfo } from '@/modules/experiment-snapshot/interfaces/interfaces'

type Props = {
  modelsInfo: ModelsInfo
}

defineProps<Props>()

const dialogPt: DialogPassThroughOptions = {
  mask: {
    style: 'align-items: flex-start; padding: 64px 0 56px;',
  },
  root: {
    style: 'width: calc(100vw - 32px); height: 100%; max-height: none;',
  },
  header: {
    style: 'padding: 16px 20px; justify-content: flex-end;',
  },
  content: {
    style: 'display: flex; padding: 0; overflow: hidden;',
  },
  pcCloseButton: {},
}

const visible = defineModel<boolean>('visible')
</script>

<style scoped>
.models {
  flex: 1 1 auto;
  overflow-x: auto;
}
</style>
