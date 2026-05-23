<template>
  <div class="iframe-wrapper">
    <iframe
      :src="url"
      :style="{ zoom: zoom / 100 }"
      sandbox="allow-scripts"
      class="iframe"
    ></iframe>
    <UiZoom
      :model-value="zoom.toString()"
      @zoom-out="zoomOut"
      @zoom-in="zoomIn"
      @update:model-value="(value) => zoomChange(Number(value))"
      class="zoom-button"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import UiZoom from '@/components/ui/UiZoom.vue'

type Props = {
  url: string
}

defineProps<Props>()

const zoom = ref(100)

function zoomOut() {
  const newZoom = zoom.value - 25
  zoom.value = Math.max(newZoom, 20)
}

function zoomIn() {
  const newZoom = zoom.value + 25
  zoom.value = Math.min(newZoom, 400)
}

function zoomChange(value: number) {
  zoom.value = value
}
</script>

<style scoped>
.iframe-wrapper {
  width: 100%;
  height: calc(100vh - 310px);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
  overflow-y: auto;
  position: relative;
}
.iframe {
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
