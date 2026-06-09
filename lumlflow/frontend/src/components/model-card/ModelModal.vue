<template>
  <Dialog
    :visible="modelCardStore.dialogVisible"
    modal
    dismissable-mask
    :draggable="false"
    :pt="DIALOG_PT"
    :header="dialogHeader"
    :style="{ height: 'calc(100vh - 115px)' }"
    @update:visible="onVisibleChange"
  >
    <Skeleton v-if="modelCardStore.modelCardLoading" class="min-h-full" />
    <div
      v-else-if="!modelCardStore.modelCardHtmlUrl"
      class="flex items-center justify-center min-h-full text-muted-color"
    >
      No model card available
    </div>
    <iframe
      v-else
      :src="modelCardStore.modelCardHtmlUrl"
      sandbox="allow-scripts"
      class="model-card-iframe"
      title="Model card"
    />
  </Dialog>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Dialog, Skeleton } from 'primevue'
import { DIALOG_PT } from './model-card.const'
import { useModelCardStore } from '@/store/model-card'

const modelCardStore = useModelCardStore()

const dialogHeader = computed(() => modelCardStore.modelData?.name ?? 'Model Card')

function onVisibleChange(visible: boolean) {
  if (!visible) {
    modelCardStore.hideModelCard()
  }
}
</script>

<style scoped>
.model-card-iframe {
  width: 100%;
  height: calc(100vh - 200px);
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
}
</style>
