<template>
  <Tag v-tooltip.top="tooltip" :severity="severity" :pt="META_TAG_PT">
    <component :is="icon" :size="14" class="shrink-0" />
    <span>{{ label }}</span>
  </Tag>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import { BadgeCheck, DatabaseZap, Globe, History, Pin, type LucideIcon } from 'lucide-vue-next'

/**
 * The small factual badges that ride next to a status chip. Each one states a
 * recorded fact the user would otherwise have to guess:
 * - cached      — memo hit; a hit is not a 0-second run
 * - older-env   — computed under a lock hash that differs from the live env
 * - settled     — branch fully materialized and consistent (a highlight, not a gate)
 * - external    — reads outside the store; unmemoizable
 * - pinned      — input frozen at fork time
 *
 * `StatusChip` beside it does the same job for the status vocabulary, and both
 * are `Tag :severity` — a second, hand-coloured chip system is how the two
 * start to drift.
 */
export type MetaBadgeVariant = 'cached' | 'older-env' | 'settled' | 'external' | 'pinned'

type Severity = 'info' | 'warn' | 'success' | 'secondary'

const props = defineProps<{ variant: MetaBadgeVariant }>()

const CONFIG: Record<
  MetaBadgeVariant,
  { label: string; tooltip: string; icon: LucideIcon; severity: Severity }
> = {
  cached: {
    label: 'cached',
    tooltip: 'a memo hit. nothing recomputed.',
    icon: DatabaseZap,
    severity: 'info',
  },
  'older-env': {
    label: 'older env',
    tooltip: 'ran under an older environment lock than the live venv',
    icon: History,
    severity: 'warn',
  },
  settled: {
    label: 'settled',
    tooltip: 'this lane is fully materialized and consistent at this point',
    icon: BadgeCheck,
    severity: 'success',
  },
  external: {
    label: 'external',
    tooltip: 'reads outside the store. the store cannot know when it changes.',
    icon: Globe,
    severity: 'secondary',
  },
  pinned: {
    label: 'pinned',
    tooltip: 'frozen when this lane started. updates are explicit accept-upstream ops.',
    icon: Pin,
    severity: 'secondary',
  },
}

const META_TAG_PT = { root: { class: 'text-sm font-normal gap-1 px-1.5 py-0 shrink-0' } }

const label = computed(() => CONFIG[props.variant].label)
const tooltip = computed(() => CONFIG[props.variant].tooltip)
const icon = computed(() => CONFIG[props.variant].icon)
const severity = computed(() => CONFIG[props.variant].severity)
</script>
