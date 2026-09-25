<script lang="ts">
import type { TrackerExperimentState } from '@/flow/api/types'
import type { AssetKind, CellStatus, StaleInfo } from '../../model/types'

/** One lens row: always addressed by the producing cell's slug. */
export interface InventoryRow {
  key: string
  slug: string
  kind: AssetKind
  title: string
  mono?: boolean
  /** Right-aligned fact, e.g. 'val_auc 0.856'. */
  detail?: string
  status?: CellStatus
  stale?: StaleInfo
  /** volatility: external — the store cannot know when its bytes change. */
  external?: boolean
  trackerState?: TrackerExperimentState
  tags?: string[]
}
</script>

<script setup lang="ts">
import { Button, Tag } from 'primevue'
import KindBadge from '../../ui/KindBadge.vue'
import MetaBadge from '../../ui/MetaBadge.vue'
import StatusChip from '../../ui/StatusChip.vue'
import TrackerStateBadge from '../../ui/TrackerStateBadge.vue'

defineProps<{ rows: InventoryRow[] }>()

const emit = defineEmits<{ select: [slug: string] }>()

const ROW_PT = { root: { class: 'w-full justify-start gap-2.5 px-1.5 py-1.5 font-normal' } }
</script>

<template>
  <ul class="flex min-w-0 flex-col">
    <li v-for="row in rows" :key="row.key" class="min-w-0">
      <Button
        text
        severity="secondary"
        size="small"
        data-testid="lens-row"
        :pt="ROW_PT"
        @click="emit('select', row.slug)"
      >
        <KindBadge :kind="row.kind" icon-only :icon-size="14" />
        <span class="min-w-0 truncate text-base" :class="row.mono ? 'font-mono' : ''">
          {{ row.title }}
        </span>
        <MetaBadge v-if="row.external" variant="external" />
        <Tag
          v-for="tag in row.tags"
          :key="tag"
          :value="tag"
          severity="secondary"
          :pt="{ root: { class: 'text-sm font-normal px-1.5 py-0' } }"
        />
        <span class="ml-auto" />
        <span v-if="row.detail" class="shrink-0 font-mono text-sm text-muted-color">
          {{ row.detail }}
        </span>
        <!-- Only deviations are chipped: a chip on every materialized row is noise. -->
        <StatusChip
          v-if="row.status && row.status !== 'materialized'"
          :status="row.status"
          :stale="row.stale"
          compact
        />
        <TrackerStateBadge v-if="row.trackerState" :state="row.trackerState" />
      </Button>
    </li>
  </ul>
</template>
