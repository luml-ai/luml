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
    <div v-else class="iframe-wrapper">
      <iframe
        :src="modelCardStore.modelCardHtmlUrl"
        :style="{ zoom: zoom / 100 }"
        sandbox="allow-scripts"
        class="model-card-iframe"
        title="Model card"
      />
      <UiZoom
        :model-value="zoom.toString()"
        class="zoom-button"
        @zoom-out="zoomOut"
        @zoom-in="zoomIn"
        @update:model-value="(value) => zoomChange(Number(value))"
      />
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Dialog, Skeleton } from 'primevue'
import { DIALOG_PT } from './model-card.const'
import { useModelCardStore } from '@/store/model-card'
import UiZoom from '@/components/ui/UiZoom.vue'

const modelCardStore = useModelCardStore()

const zoom = ref(100)

const dialogHeader = computed(() => modelCardStore.modelData?.name ?? 'Model Card')

function zoomOut() {
  zoom.value = Math.max(zoom.value - 25, 20)
}

function zoomIn() {
  zoom.value = Math.min(zoom.value + 25, 400)
}

function zoomChange(value: number) {
  if (!Number.isFinite(value)) {
    return
  }
  zoom.value = Math.min(Math.max(value, 20), 400)
}

function onVisibleChange(visible: boolean) {
  if (!visible) {
    modelCardStore.hideModelCard()
    zoom.value = 100
  }
}
</script>

<style scoped>
.iframe-wrapper {
  width: 100%;
  height: calc(100vh - 200px);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--p-card-shadow);
  overflow: auto;
  position: relative;
}
.model-card-iframe {
  width: 100%;
  min-height: 100%;
  border: none;
  outline: none;
  display: block;
}
.zoom-button {
  position: absolute;
  top: 10px;
  right: 10px;
}
</style>
