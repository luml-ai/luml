<template>
  <div class="flex shrink-0 items-center gap-0.5">
    <PreflightPopover
      v-if="!cell.isNote && cell.status !== 'running'"
      :preflight="preflight ?? null"
      :target="cell.slug"
      @open="emit('preflight')"
      @run="emit('run', $event)"
    />
    <Button
      v-if="!cell.isNote && cell.status === 'running'"
      v-tooltip.top="stopTooltip"
      text
      rounded
      severity="danger"
      size="small"
      :aria-label="stopTooltip"
      @click="emit('stop')"
    >
      <template #icon><Square :size="14" /></template>
    </Button>

    <!--
      Two controls per row, and the rest one click away: nine cards on a canvas
      carried forty-five icon buttons, which is more chrome than the work.
    -->
    <span ref="moreAnchor" class="inline-flex">
      <Button
        v-tooltip.top="'more'"
        text
        rounded
        severity="secondary"
        size="small"
        aria-label="more"
        aria-haspopup="menu"
        @click="menu?.toggle($event)"
      >
        <template #icon><EllipsisVertical :size="14" /></template>
      </Button>
    </span>
    <Menu ref="menu" :model="menuItems" popup>
      <template #itemicon="{ item }">
        <component :is="(item as CellMenuItem).glyph" :size="14" class="shrink-0" />
      </template>
    </Menu>

    <HandoffPopover
      ref="handoffPopover"
      :cell="cell"
      gesture="explain"
      :branch="branch"
      :handoff="handoff"
      @send-to-agent="emit('send-to-agent', $event)"
    />

    <Popover ref="confirmPopover">
      <div class="flex w-72 flex-col gap-2.5">
        <p class="text-base">
          delete <code class="font-mono">{{ cell.slug }}</code> from this lane?
        </p>
        <p class="text-sm text-muted-color">other lanes keep it</p>
        <div class="flex justify-end gap-2">
          <Button text severity="secondary" label="keep" @click="confirmPopover?.hide()" />
          <Button severity="danger" label="delete from this lane" @click="confirmDelete" />
        </div>
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import { Button, Menu, Popover } from 'primevue'
import type { MenuItem } from 'primevue/menuitem'
import {
  CloudUpload,
  Copy,
  EllipsisVertical,
  Maximize2,
  Plus,
  Send,
  Square,
  TextCursorInput,
  Trash2,
  Zap,
  type LucideIcon,
} from 'lucide-vue-next'
import type { HandoffGesture } from '@/flow/api/types'
import type { FlowCell, Preflight } from '../../model/types'
import HandoffPopover from '../handoff/HandoffPopover.vue'
import PreflightPopover from './PreflightPopover.vue'

/**
 * The op row: the run and everything else. Every verb is mapped to a daemon op
 * and each is honest about scope: the preflight before any run, awaiter-aware
 * stop wording, a per-lane delete confirm, duplicate buried in the menu.
 */

/** A `Menu` model row carrying the glyph the `#itemicon` slot renders. */
type CellMenuItem = MenuItem & { glyph?: LucideIcon }
const props = defineProps<{
  cell: FlowCell
  density: 'canvas' | 'notebook'
  awaiters?: number
  preflight?: Preflight | null
  branch?: string
  /** The daemon's explain payload, once it has answered the popover's open. */
  handoff?: string | null
}>()

const emit = defineEmits<{
  run: [payload: { force: boolean }]
  /** The run closure is wanted — asked for when the popover opens, not before. */
  preflight: []
  stop: []
  expand: []
  handoff: [gesture: HandoffGesture]
  'send-to-agent': [payload: string]
  rename: []
  delete: []
  duplicate: []
  'add-downstream': []
  promote: []
  eager: [on: boolean]
}>()

const menu = useTemplateRef<InstanceType<typeof Menu>>('menu')
const confirmPopover = useTemplateRef<InstanceType<typeof Popover>>('confirmPopover')
const handoffPopover = useTemplateRef<InstanceType<typeof HandoffPopover>>('handoffPopover')
const moreAnchor = useTemplateRef<HTMLElement>('moreAnchor')

const awaiters = computed(() => props.awaiters ?? 0)

// Preemption fires only when no awaiter still wants the result; when other
// branches await the run, stop only requeues this branch.
const stopTooltip = computed(() => {
  const others = awaiters.value
  if (others === 0) return 'stop the run'
  const branches =
    others === 1 ? '1 other lane still waits' : `${others} other lanes still wait`
  return `leave the run, requeue this lane. ${branches} for it.`
})

const hasInlineAsset = computed(() =>
  props.cell.outputs.some((output) => output.declared === 'asset'),
)

/**
 * Four groups, in the order a reader reaches for them: look at it, change it,
 * move its value, destroy it. Nothing here is a sentence — a menu is scanned,
 * not read, and the two labels that carried caveats ("mints a new identity with
 * no consumers", "materialize and download · ~2.4s") were the reason this one
 * could not be. `download` is not among them: `expand` is the item above, and
 * the drawer it opens carries the download for the output on screen, with the
 * same materialize-first wording. Eight is the ceiling and a note cell sees
 * five.
 */
const menuItems = computed<CellMenuItem[]>(() => {
  const items: CellMenuItem[] = [
    { label: 'expand', glyph: Maximize2, command: () => emit('expand') },
    {
      label: 'send to agent',
      glyph: Send,
      command: (event) => {
        emit('handoff', 'explain')
        handoffPopover.value?.show(event.originalEvent, moreAnchor.value)
      },
    },
    { separator: true },
    { label: 'rename', glyph: TextCursorInput, command: () => emit('rename') },
  ]
  if (!props.cell.isNote) {
    items.push({ label: 'add cell downstream', glyph: Plus, command: () => emit('add-downstream') })
  }
  items.push({ label: 'duplicate', glyph: Copy, command: () => emit('duplicate') })
  if (!props.cell.isNote) {
    items.push({ separator: true })
    if (hasInlineAsset.value)
      items.push({ label: 'promote to LUML', glyph: CloudUpload, command: () => emit('promote') })
    items.push({
      label: props.cell.eager ? 'eager materialization · on' : 'eager materialization · off',
      glyph: Zap,
      command: () => emit('eager', !props.cell.eager),
    })
  }
  items.push({ separator: true })
  items.push({
    label: 'delete from this lane…',
    glyph: Trash2,
    class: 'flow-menu-danger',
    command: (event) => {
      confirmPopover.value?.show(event.originalEvent, moreAnchor.value)
    },
  })
  return items
})

function confirmDelete(): void {
  emit('delete')
  confirmPopover.value?.hide()
}
</script>

<!--
  Unscoped on purpose: the menu is teleported to `body`, so a scoped rule never
  reaches the row PrimeVue renders. The destructive item is the one place in the
  menu that carries colour, and it reads it from the theme rather than a palette.
-->
<style>
.flow-menu-danger .p-menu-item-content {
  color: var(--p-message-error-color);
}
</style>
