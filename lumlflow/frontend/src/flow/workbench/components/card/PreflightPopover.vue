<template>
  <Button
    v-tooltip.top="'run'"
    text
    :rounded="!label"
    :severity="label ? undefined : 'secondary'"
    :label="label"
    aria-label="run"
    @click="reveal"
  >
    <template #icon><Play :size="14" /></template>
  </Button>

  <Popover ref="popover">
    <div class="w-80 flex flex-col gap-3">
      <div>
        <p class="text-base">
          run <code class="font-mono">{{ target }}</code>
        </p>
      </div>

      <p v-if="!preflight" class="text-sm text-muted-color">estimating…</p>

      <template v-else>
        <div v-if="preflight.cached.length" class="flex flex-col gap-1">
          <p class="text-sm text-muted-color">cached</p>
          <div class="flex flex-wrap gap-1.5">
            <code
              v-for="slug in preflight.cached"
              :key="slug"
              class="font-mono text-sm px-1.5 py-0.5 rounded-lg bg-surface-100 dark:bg-surface-800 text-muted-color"
            >
              {{ slug }}
            </code>
          </div>
        </div>

        <div class="flex flex-col gap-1">
          <p class="text-sm text-muted-color">recomputes</p>
          <p v-if="!preflight.recompute.length" class="text-sm text-muted-color">
            nothing · all current
          </p>
          <div
            v-for="slug in preflight.recompute"
            :key="slug"
            class="flex items-center justify-between gap-3"
          >
            <code class="font-mono text-sm">{{ slug }}</code>
            <span v-if="untimed.has(slug)" class="text-sm text-muted-color">never timed</span>
          </div>
          <div
            v-if="preflight.recompute.length"
            class="flex items-center justify-between gap-3 border-t border-surface-200 dark:border-surface-700 pt-1 mt-0.5"
          >
            <span class="text-sm">{{ untimed.size ? 'total · timed only' : 'total' }}</span>
            <span class="text-sm font-medium">{{ formatCost(preflight.totalSeconds) }}</span>
          </div>
        </div>

        <p
          v-for="reason in preflight.reasons"
          :key="reason"
          class="text-sm text-muted-color"
        >
          {{ reason }}
        </p>
      </template>

      <label class="flex items-center gap-2 text-sm cursor-pointer" :for="forceId">
        <Checkbox v-model="force" :input-id="forceId" binary />
        <span>force rerun</span>
      </label>

      <Button :label="runLabel" class="w-full" @click="confirmRun" />
    </div>
  </Popover>
</template>

<script setup lang="ts">
import { computed, ref, useId, useTemplateRef } from 'vue'
import { Button, Checkbox, Popover } from 'primevue'
import { Play } from 'lucide-vue-next'
import { formatCost, formatCount } from '../../model/format'
import type { Preflight } from '../../model/types'

/**
 * Run never happens blind: the closure (what is cached, what recomputes, and
 * the total seconds) is on screen before the click. Force-rerun is a labeled
 * modifier, never the default.
 *
 * The closure is the daemon's to compute, so opening the popover asks for it
 * and the answer lands under the reader. Until it does the popover says it is
 * still asking; a placeholder closure would be a cost estimate nobody made.
 */
const props = defineProps<{
  preflight: Preflight | null
  target: string
  /** Optional trigger label; without it the trigger is an icon button. */
  label?: string
}>()

const emit = defineEmits<{
  run: [payload: { force: boolean }]
  /** Opened — the moment the closure is worth asking the daemon for. */
  open: []
}>()

const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')
const force = ref(false)
const forceId = useId()

const untimed = computed(() => new Set(props.preflight?.unknown ?? []))

const runLabel = computed(() => {
  if (!props.preflight) return 'run'
  const { cached, recompute, totalSeconds } = props.preflight
  if (force.value && cached.length > 0) {
    // Memo hits recompute too; their cost is unknown, so the total is open-ended.
    return `run ${formatCount(recompute.length + cached.length, 'cell')} · ~${formatCost(totalSeconds)}+`
  }
  return `run ${formatCount(recompute.length, 'cell')} · ~${formatCost(totalSeconds)}`
})

function reveal(event: Event): void {
  emit('open')
  popover.value?.toggle(event)
}

function confirmRun(): void {
  emit('run', { force: force.value })
  force.value = false
  popover.value?.hide()
}
</script>
