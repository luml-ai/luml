<template>
  <div class="h-full overflow-y-auto">
    <div class="mx-auto flex w-full max-w-[780px] flex-col gap-4 px-1 pb-16">
      <div
        v-for="cell in ordered"
        :key="cell.slug"
        :ref="(el) => registerCard(cell.slug, el)"
        class="rounded-lg"
        :class="tintedSlugs.has(cell.slug) ? 'ring-1 ring-(--p-message-warn-color)' : ''"
        @click="emit('select', cell.slug)"
      >
        <!-- Same slot contract as the canvas: the two views cannot show
             different cards for the same cell. -->
        <slot
          name="card"
          :cell="cell"
          :selected="cell.slug === selectedSlug"
          :preflight="preflights[cell.slug]"
        >
          <CellCard
            :cell="cell"
            density="notebook"
            :selected="cell.slug === selectedSlug"
            :branch="branch"
            :preflight="preflights[cell.slug]"
            @expand="emit('expand', cell.slug)"
            @run="emit('run', cell.slug, $event)"
            @stop="emit('stop', cell.slug)"
            @rename="emit('rename', cell.slug)"
            @delete="emit('delete', cell.slug)"
            @duplicate="emit('duplicate', cell.slug)"
            @send-to-agent="emit('send-to-agent', cell.slug, $event)"
            @resolve-conflict="emit('resolve-conflict', cell.slug, $event)"
            @edit="emit('edit', cell.slug, $event)"
          />
        </slot>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, watch, type ComponentPublicInstance } from 'vue'
import { topologicalOrder } from '../model/registry'
import type { FlowCell, Preflight } from '../model/types'
import CellCard from '../components/card/CellCard.vue'

/**
 * The notebook view: the same branch slice and the same cards as the canvas,
 * one centered column, code accented. Order is topological with authoring-step
 * tiebreaks, so cards never reorder when an unrelated cell lands.
 */
const props = defineProps<{
  cells: FlowCell[]
  branch: string
  selectedSlug: string | null
  tintedSlugs: Set<string>
  preflights: Record<string, Preflight | undefined>
}>()

const emit = defineEmits<{
  select: [slug: string]
  expand: [slug: string]
  run: [slug: string, payload: { force: boolean }]
  stop: [slug: string]
  rename: [slug: string]
  delete: [slug: string]
  duplicate: [slug: string]
  'send-to-agent': [slug: string, payload: string]
  'resolve-conflict': [slug: string, choice: 'overwrite' | 'fork']
  edit: [slug: string, payload: { source: string }]
}>()

const ordered = computed(() => topologicalOrder(props.cells))

const cards = new Map<string, HTMLElement>()

function registerCard(slug: string, el: Element | ComponentPublicInstance | null): void {
  if (el instanceof HTMLElement) cards.set(slug, el)
  else cards.delete(slug)
}

function scrollToSelected(smooth: boolean): void {
  if (!props.selectedSlug) return
  const el = cards.get(props.selectedSlug)
  el?.scrollIntoView?.({ behavior: smooth ? 'smooth' : 'auto', block: 'center' })
}

onMounted(() => scrollToSelected(false))

watch(
  () => props.selectedSlug,
  () => scrollToSelected(true),
)
</script>
