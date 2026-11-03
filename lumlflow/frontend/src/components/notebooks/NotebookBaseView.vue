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
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
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

// Cells above the revealed one keep growing for a moment after it is scrolled
// to (code editors, tables and charts render late), which pushed it out of
// view. Hold it at the top while they settle; the user's own scroll lets go.
const SETTLE_MS = 1500
let releaseAnchor: (() => void) | null = null

function scrollToCell(wrapper: HTMLElement, cellEl: HTMLElement, behavior: ScrollBehavior) {
  const offset = cellEl.getBoundingClientRect().top - wrapper.getBoundingClientRect().top
  if (Math.abs(offset) < 1) return
  wrapper.scrollTo({ top: wrapper.scrollTop + offset, behavior })
}

function anchorCell(wrapper: HTMLElement, cellEl: HTMLElement) {
  releaseAnchor?.()
  const observer = new ResizeObserver(() => scrollToCell(wrapper, cellEl, 'auto'))
  for (const child of wrapper.children) observer.observe(child)
  const release = () => {
    observer.disconnect()
    clearTimeout(timer)
    for (const event of USER_SCROLL_EVENTS) wrapper.removeEventListener(event, release)
    if (releaseAnchor === release) releaseAnchor = null
  }
  const timer = setTimeout(release, SETTLE_MS)
  for (const event of USER_SCROLL_EVENTS) {
    wrapper.addEventListener(event, release, { passive: true, once: true })
  }
  releaseAnchor = release
}

const USER_SCROLL_EVENTS = ['wheel', 'touchstart', 'keydown', 'mousedown'] as const

onBeforeUnmount(() => releaseAnchor?.())

function revealCell(id: string) {
  const wrapper = wrapperRef.value
  const cellEl = cellRefs.get(id)
  if (!wrapper || !cellEl) return
  scrollToCell(wrapper, cellEl, 'smooth')
  anchorCell(wrapper, cellEl)
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
  /* Room for the scrollbar, so it never sits on top of a card's border. */
  padding-right: 10px;
  scrollbar-gutter: stable;
  margin-bottom: -20px;
  transition: height 0.2s ease;
}
</style>
