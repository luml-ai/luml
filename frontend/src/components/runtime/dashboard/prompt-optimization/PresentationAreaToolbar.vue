<template>
  <div class="toolbar">
    <div class="toolbar-body">
      <div class="toolbar-zoom">
        <Button
          class="smallest-button"
          variant="text"
          severity="secondary"
          size="small"
          @click="() => zoomOutFunction()"
        >
          <template #icon>
            <ZoomOut :size="14" />
          </template>
        </Button>
        <div class="toolbar-zoom-value">
          <input v-model="zoomValue" type="number" class="toolbar-zoom-input" @input="changeZoom" />
          <span class="toolbar-zoom-value">%</span>
        </div>
        <Button
          class="smallest-button"
          variant="text"
          severity="secondary"
          size="small"
          @click="() => zoomInFunction()"
        >
          <template #icon>
            <ZoomIn :size="14" />
          </template>
        </Button>
      </div>
      <div class="pointers">
        <Button
          class="small-button"
          variant="text"
          :severity="cursorMode === 'hand' ? 'primary' : 'secondary'"
          size="small"
          @click="cursorMode = 'hand'"
        >
          <template #icon>
            <Pointer :size="14" />
          </template>
        </Button>
        <Button
          class="small-button"
          variant="text"
          :severity="cursorMode === 'pointer' ? 'primary' : 'secondary'"
          size="small"
          @click="cursorMode = 'pointer'"
        >
          <template #icon>
            <MousePointer2 :size="14" />
          </template>
        </Button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useVueFlow } from '@vue-flow/core'
import { computed, ref, watch } from 'vue'
import { Button } from 'primevue'
import { MousePointer2, Pointer, ZoomIn, ZoomOut } from 'lucide-vue-next'

const {
  zoomIn: zoomInFunction,
  zoomOut: zoomOutFunction,
  zoomTo,
  viewport,
  panOnDrag,
} = useVueFlow()

const zoomValue = ref((viewport.value.zoom * 100).toFixed())
const cursorMode = ref<'pointer' | 'hand'>('hand')

const isViewportLocked = computed(() => cursorMode.value === 'pointer')

function changeZoom(e: Event) {
  const target = e.target as HTMLInputElement
  const value = !isNaN(Number(target.value)) ? Number(target.value) / 100 : 0
  zoomTo(value)
}

watch(
  () => viewport.value.zoom,
  (value) => {
    zoomValue.value = (value * 100).toFixed()
  },
)

watch(
  isViewportLocked,
  (val) => {
    panOnDrag.value = !val
  },
  { immediate: true },
)
</script>

<style scoped>
.toolbar {
  position: absolute;
  bottom: 16px;
  left: 50%;
  transform: translateX(-50%);
}

.toolbar-body {
  box-shadow: var(--card-shadow);
  border-radius: 8px;
  background-color: var(--p-card-background);
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.toolbar-zoom {
  border-radius: 8px;
  border: 0.5px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
}

.toolbar-zoom-value {
  font-size: 12px;
}

.pointers {
  display: flex;
  align-items: center;
  gap: 6px;
}

.toolbar-zoom-input {
  width: auto;
  min-width: 0;
  border: none;
  outline: none;
  font-family: 'Inter', sans-serif;
  color: var(--p-text-color);
  display: inline-block;
  width: 23px;
  font-size: 12px;
}
</style>
