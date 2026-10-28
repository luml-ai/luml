<template>
  <div ref="wrapperRef" class="wrapper" @click.self="flowStore.selectCell(null)">
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
      @click="flowStore.selectCell(cell.asset.id, { reveal: false })"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import {
  NOTEBOOK_ASSET_ICONS,
} from '@/components/notebooks/notebooks.const'
import { useFlowStore } from '@/store/flow'
import NotebookCell from '@/components/notebooks/cell/NotebookCell.vue'

const flowStore = useFlowStore()

const wrapperHeight = 'calc(100vh - 211px)'

const cells = computed(() => {
  const bySlug = new Map(flowStore.cells.map((cell) => [cell.slug, cell]))
  return flowStore.notebookCells.flatMap((asset) => {
    const cell = bySlug.get(asset.id)
    return cell ? [{ asset, ...cell }] : []
  })
})

const wrapperRef = ref<HTMLElement | null>(null)
const cellRefs = new Map<string, HTMLElement>()

function setCellRef(id: string, el: unknown) {
  if (el && typeof el === 'object' && '$el' in el) {
    cellRefs.set(id, (el as { $el: HTMLElement }).$el)
  } else {
    cellRefs.delete(id)
  }
}

function revealCell(id: string) {
  const wrapper = wrapperRef.value
  const cellEl = cellRefs.get(id)
  if (!wrapper || !cellEl) return
  const offset = cellEl.getBoundingClientRect().top - wrapper.getBoundingClientRect().top
  wrapper.scrollTo({ top: wrapper.scrollTop + offset, behavior: 'smooth' })
  cellEl.animate?.(
    [
      { outline: '3px solid var(--p-primary-color)', outlineOffset: '-3px' },
      { outline: '3px solid transparent', outlineOffset: '-3px' },
    ],
    { duration: 1200, easing: 'ease-out' },
  )
}

watch(
  () => flowStore.revealedCell,
  async (request) => {
    if (!request) return
    await nextTick()
    revealCell(request.id)
    flowStore.clearRevealedCell()
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
