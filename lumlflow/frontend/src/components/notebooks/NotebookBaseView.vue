<template>
  <div class="wrapper">
    <NotebookCell
      v-for="cell in cells"
      :key="cell.asset.id"
      :ref="(el) => setCellRef(cell.asset.id, el)"
      class="not-last:mb-2"
      :class="{ 'border-primary!': cell.asset.id === flowStore.selectedCellId }"
      :title="cell.asset.name"
      :icon="NOTEBOOK_ASSET_ICONS[cell.asset.type]"
      :cost-seconds="cell.cost_seconds"
      :state="cell.state"
      :causes="cell.causes"
      :reused="cell.reused"
      :cell="cell"
      @click="flowStore.selectCell(cell.asset.id)"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, watch } from 'vue'
import {
  NOTEBOOK_ASSET_ICONS,
  NOTEBOOK_TERMINAL_HEIGHT,
} from '@/components/notebooks/notebooks.const'
import { useFlowStore } from '@/store/flow'
import NotebookCell from '@/components/notebooks/cell/NotebookCell.vue'

const flowStore = useFlowStore()

const wrapperHeight = computed(() =>
  flowStore.isTerminalOpen
    ? `calc(100vh - 211px - ${NOTEBOOK_TERMINAL_HEIGHT}px - 8px)`
    : 'calc(100vh - 211px)',
)

const cells = computed(() => {
  const bySlug = new Map(flowStore.cells.map((cell) => [cell.slug, cell]))
  return flowStore.notebookCells.flatMap((asset) => {
    const cell = bySlug.get(asset.id)
    return cell ? [{ asset, ...cell }] : []
  })
})

const cellRefs = new Map<string, HTMLElement>()

function setCellRef(id: string, el: unknown) {
  if (el && typeof el === 'object' && '$el' in el) {
    cellRefs.set(id, (el as { $el: HTMLElement }).$el)
  } else {
    cellRefs.delete(id)
  }
}

watch(
  () => flowStore.selectedCellId,
  async (id) => {
    if (!id) return
    await nextTick()
    cellRefs.get(id)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  },
  { immediate: true },
)
</script>

<style scoped>
.wrapper {
  height: v-bind(wrapperHeight);
  overflow-y: auto;
  margin-bottom: -20px;
  transition: height 0.2s ease;
}
</style>
