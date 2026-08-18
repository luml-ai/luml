<template>
  <div class="toolbar">
    <div class="toolbar-body">
      <UiZoom
        v-model="zoom"
        @zoom-out="zoomOutFunction"
        @zoom-in="zoomInFunction"
        @zoom-change="zoomTo"
      />
      <UiPointerSelect v-model="cursorMode" />
      <Divider layout="vertical" class="divider" />
      <Button
        v-tooltip.top="'Link an artifact'"
        class="small-button"
        variant="text"
        severity="secondary"
        size="small"
        @click="lineageStore.setCreatorVisible(true)"
      >
        <template #icon>
          <CirclePlus :size="14" />
        </template>
      </Button>
    </div>
    <!--<OnClickOutside
      v-if="isMenuOpen"
      :options="{ ignore: [toggleMenuButton] }"
      class="menu"
      @trigger="onMenuOutsideClick"
    >
      <button class="menu-item" @click.stop="addNode(NodeTypeEnum.gate)">
        <component
          :is="PROMPT_NODES_ICONS.gate"
          :size="14"
          color="var(--p-badge-success-background)"
        />
        <span>Gate</span>
      </button>
      <Divider :style="{ margin: '2px 0' }" />
      <button class="menu-item" @click.stop="addNode(NodeTypeEnum.processor)">
        <component :is="PROMPT_NODES_ICONS.cpu" :size="14" color="var(--p-badge-warn-background)" />
        <span>Processor</span>
      </button>
    </OnClickOutside>-->
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Button, Divider } from 'primevue'
import { CirclePlus } from 'lucide-vue-next'
import { useVueFlow } from '@vue-flow/core'
import UiZoom from '../ui/UiZoom.vue'
import UiPointerSelect from '../ui/UiPointerSelect.vue'
import { useLineageStore } from '@/stores/lineage'

const lineageStore = useLineageStore()
const {
  zoomIn: zoomInFunction,
  zoomOut: zoomOutFunction,
  zoomTo,
  viewport,
  panOnDrag,
} = useVueFlow()

const zoom = ref((viewport.value.zoom * 100).toFixed())
const cursorMode = ref<'pointer' | 'hand'>('pointer')

const isViewportLocked = computed(() => cursorMode.value === 'pointer')

watch(
  () => viewport.value.zoom,
  (value) => {
    zoom.value = (value * 100).toFixed()
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
.toolbar-body {
  box-shadow: var(--card-shadow);
  border-radius: 8px;
  background-color: var(--p-card-background);
  padding: 4px 8px;
  display: flex;
  align-items: center;
  gap: 8px;
}
.divider {
  margin: 0 4px;
}
.small-button {
  padding: 4px;
  width: auto;
  height: auto;
}
</style>
