<template>
  <div class="toolbar">
    <div class="toolbar-body">
      <UiZoom
        v-model="zoomValue"
        @zoom-out="zoomOutFunction"
        @zoom-in="zoomInFunction"
        @zoom-change="zoomTo"
      />
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
import { MousePointer2, Pointer } from 'lucide-vue-next'
import UiZoom from '@/components/ui/UiZoom.vue'

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

.pointers {
  display: flex;
  align-items: center;
  gap: 6px;
}
</style>
