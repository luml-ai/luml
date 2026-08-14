<template>
  <div v-if="counts.length" class="flex min-w-0 items-center">
    <Button
      text
      severity="secondary"
      :pt="TRIGGER_PT"
      aria-haspopup="dialog"
      data-testid="stale-summary"
      @click="details?.toggle($event)"
    >
      <TriangleAlert :size="14" class="shrink-0 text-(--p-message-warn-color)" />
      <span class="truncate">{{ counts.join(' · ') }}</span>
    </Button>

    <!--
      The count is the fact; the cause and the downstream lens are what a reader
      asks for next, and asking is a click. A branch mid-edit is the ordinary
      state of this product — it does not get a page-wide colour field.
    -->
    <Popover ref="details">
      <div class="flex w-80 flex-col gap-2.5">
        <p v-if="cause" class="text-sm text-muted-color">
          first cause: <span v-html="causeHtml" />
        </p>
        <p v-if="unmaterialized" class="text-sm text-muted-color">
          {{ formatCount(unmaterialized, 'cell') }} never materialized. no baseline to compare
          against.
        </p>
        <label
          v-if="downstream"
          class="flex cursor-pointer items-center gap-2 text-base"
          :for="tintToggleId"
        >
          <ToggleSwitch v-model="showTint" :input-id="tintToggleId" />
          highlight downstream
        </label>
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { computed, useId, useTemplateRef } from 'vue'
import { Button, Popover, ToggleSwitch } from 'primevue'
import { TriangleAlert } from 'lucide-vue-next'
import { formatCount } from '../../model/format'

/**
 * What the branch owes, in one line of the bar that already names the branch.
 *
 * This was a full-width amber `Message` above the canvas — 1400 px of warn
 * background for a two-word count, on a screen where every stale cell already
 * carries its own chip and the left panel lists them. Scale follows scope: a
 * page-wide colour field belongs to connection-level states (lumlflow stopped,
 * the files held by someone else), never to work in progress.
 */
const props = defineProps<{
  /** Cells stale from a cause of their own. */
  unsynced: number
  /** Stale only because something upstream is — the toggle's subject. */
  downstream: number
  /** No recorded result anywhere; counted apart, never a flavour of stale. */
  unmaterialized: number
  /** The first stale cell's own words, e.g. 'you edited it'. */
  cause?: string
}>()

const showTint = defineModel<boolean>('showTint', { default: false })

const details = useTemplateRef<InstanceType<typeof Popover>>('details')
const tintToggleId = useId()

const counts = computed(() => {
  const parts: string[] = []
  if (props.unsynced) parts.push(`${props.unsynced} stale`)
  if (props.downstream) parts.push(`${props.downstream} downstream`)
  if (props.unmaterialized) parts.push(`${props.unmaterialized} never materialized`)
  return parts
})

const TRIGGER_PT = { root: { class: 'gap-1.5 px-2 font-normal' } }

/** Slugs inside a cause are addresses, and addresses are mono. */
const causeHtml = computed(() =>
  (props.cause ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono">$1</code>'),
)
</script>
