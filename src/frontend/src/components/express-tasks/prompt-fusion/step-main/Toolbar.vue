<template>
  <div class="toolbar">
    <div class="toolbar-body">
      <div class="toolbar-zoom">
        <d-button
          class="smallest-button"
          variant="text"
          severity="secondary"
          size="small"
          @click="zoomOutFunction"
        >
          <template #icon>
            <zoom-out :size="14" />
          </template>
        </d-button>
        <div class="toolbar-zoom-value">
          <input v-model="zoomValue" type="number" class="toolbar-zoom-input" @input="changeZoom" />
          <span class="toolbar-zoom-value">%</span>
        </div>
        <d-button
          class="smallest-button"
          variant="text"
          severity="secondary"
          size="small"
          @click="zoomInFunction"
        >
          <template #icon>
            <zoom-in :size="14" />
          </template>
        </d-button>
      </div>
      <div class="pointers">
        <d-button
          class="small-button"
          variant="text"
          :severity="cursorMode === 'hand' ? 'primary' : 'secondary'"
          size="small"
          @click="cursorMode = 'hand'"
        >
          <template #icon>
            <pointer :size="14" />
          </template>
        </d-button>
        <d-button
          class="small-button"
          variant="text"
          :severity="cursorMode === 'pointer' ? 'primary' : 'secondary'"
          size="small"
          @click="cursorMode = 'pointer'"
        >
          <template #icon>
            <mouse-pointer-2 :size="14" />
          </template>
        </d-button>
      </div>
      <d-divider layout="vertical" class="divider" />
      <d-button
        ref="toggleMenuButton"
        v-tooltip.top="'Add card'"
        class="small-button"
        variant="text"
        severity="secondary"
        size="small"
        @click="toggleMenu"
      >
        <template #icon>
          <circle-plus :size="14" />
        </template>
      </d-button>
    </div>
    <on-click-outside
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
      <d-divider :style="{ margin: '2px 0' }" />
      <button class="menu-item" @click.stop="addNode(NodeTypeEnum.processor)">
        <component :is="PROMPT_NODES_ICONS.cpu" :size="14" color="var(--p-badge-warn-background)" />
        <span>Processor</span>
      </button>
    </on-click-outside>
  </div>
</template>

<script setup lang="ts">
import { ZoomIn, ZoomOut, Pointer, MousePointer2, CirclePlus } from 'lucide-vue-next'
import { useVueFlow } from '@vue-flow/core'
import { computed, ref, watch } from 'vue'
import { NodeTypeEnum, PROMPT_NODES_ICONS } from '../interfaces'
import { OnClickOutside } from '@vueuse/components'
import { getEmptyGateNode, getEmptyProcessorNode } from '@/constants/prompt-fusion'

const {
  zoomIn: zoomInFunction,
  zoomOut: zoomOutFunction,
  zoomTo,
  viewport,
  addNodes,
  panOnDrag,
} = useVueFlow()

const zoomValue = ref((viewport.value.zoom * 100).toFixed())
const cursorMode = ref<'pointer' | 'hand'>('pointer')
const toggleMenuButton = ref<HTMLButtonElement>()
const isMenuOpen = ref(false)
const isViewportLocked = computed(() => cursorMode.value === 'pointer')

const toggleMenu = () => {
  isMenuOpen.value = !isMenuOpen.value
}
function changeZoom(e: Event) {
  const target = e.target as HTMLInputElement
  const value = !isNaN(Number(target.value)) ? Number(target.value) / 100 : 0
  zoomTo(value)
}
function onMenuOutsideClick() {
  if (isMenuOpen.value) toggleMenu()
}
function addNode(node: NodeTypeEnum) {
  isMenuOpen.value = false
  if (node === NodeTypeEnum.gate) {
    addNodes(getEmptyGateNode())
  } else if (node === NodeTypeEnum.processor) {
    addNodes(getEmptyProcessorNode())
  }
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
  bottom: -15px;
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
.smallest-button {
  padding: 2px;
  width: auto;
  height: auto;
}
.small-button {
  padding: 4px;
  width: auto;
  height: auto;
}
.divider {
  margin: 0 4px;
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
.menu {
  max-width: 175px;
  width: 100%;
  background-color: var(--p-card-background);
  border: 1px solid var(--p-menu-border-color);
  border-radius: var(--p-menu-border-radius);
  padding: 4px;
  box-shadow:
    0px 4px 6px -1px rgba(0, 0, 0, 0.1),
    0px 2px 4px -2px rgba(0, 0, 0, 0.1);
  position: absolute;
  bottom: calc(100% + 7px);
  right: 0;
}
.menu-item {
  padding: 8px 12px;
  color: var(--p-menu-item-color);
  width: 100%;
  transition:
    background-color var(--p-menu-transition-duration),
    color var(--p-menu-transition-duration);
  border-radius: var(--p-menu-item-border-radius);
  cursor: pointer;
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: var(--p-menu-item-gap);
}
.menu-item:hover {
  background-color: var(--p-menu-item-focus-background);
}
</style>
