<template>
  <div class="toolbar">
    <UiZoom
      v-model="zoom"
      :align="'vertical'"
      @zoom-in="emit('zoomIn')"
      @zoom-out="emit('zoomOut')"
      @zoom-change="(value) => emit('zoomChange', value)"
    />
    <div class="pointers">
      <Button
        class="pointer-button"
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
        class="pointer-button"
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
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { Button } from 'primevue'
import { Pointer, MousePointer2 } from 'lucide-vue-next'
import UiZoom from '@/components/ui/UiZoom.vue'

interface Emits {
  zoomIn: []
  zoomOut: []
  zoomChange: [value: number]
}

const emit = defineEmits<Emits>()

const zoom = defineModel<string>('zoom', { required: true })

const { panOnDrag } = useVueFlow()

const cursorMode = ref<'pointer' | 'hand'>('pointer')
const isViewportLocked = computed(() => cursorMode.value === 'pointer')

watch(
  isViewportLocked,
  (val) => {
    panOnDrag.value = !val
  },
  { immediate: true },
)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.toolbar {
  @apply bottom-4 right-4 absolute bg-(--p-card-background) shadow-(--p-card-shadow) p-2 rounded-lg flex flex-col items-center gap-2;
}
.pointers {
  @apply flex flex-col items-center gap-1.5;
}
.pointer-button {
  @apply p-1! w-auto! h-auto!;
}
</style>
