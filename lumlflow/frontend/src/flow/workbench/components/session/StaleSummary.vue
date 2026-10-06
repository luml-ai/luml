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

const props = defineProps<{
  unsynced: number
  downstream: number
  unmaterialized: number
  waitingOnThreshold?: number
  neverTimed?: number
  blockedByFailure?: number
  refreshFailed?: number
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
  if (props.waitingOnThreshold) parts.push(`${props.waitingOnThreshold} waiting on threshold`)
  if (props.neverTimed) parts.push(`${props.neverTimed} never timed`)
  if (props.blockedByFailure) parts.push(`${props.blockedByFailure} blocked by a failure`)
  if (props.refreshFailed) parts.push(`${props.refreshFailed} could not refresh`)
  return parts
})

const TRIGGER_PT = { root: { class: 'gap-1.5 px-2 font-normal' } }

const causeHtml = computed(() =>
  (props.cause ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/`([^`]+)`/g, '<code class="font-mono">$1</code>'),
)
</script>
