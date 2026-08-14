<template>
  <Tag
    :severity="instant ? 'success' : 'warn'"
    :value="headline"
    :title="detail"
    :pt="CHIP_PT"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import { formatCost } from '../engine'
import type { PreflightCost } from '../types'

/**
 * What a state change costs, shown *before* the click.
 *
 * "Materializes from cache, instant" versus "recomputes TrainGBM, ~2h" is the
 * difference between the warm-process promise being honest and being marketing.
 */
const props = defineProps<{ cost: PreflightCost }>()

const CHIP_PT = { root: { class: 'px-2 py-0.5 text-xs font-normal' } }

const instant = computed(() => props.cost.recomputeAssetIds.length === 0)

const headline = computed(() =>
  instant.value
    ? `${props.cost.cachedAssetIds.length} from cache · instant`
    : `recomputes ${props.cost.recomputeAssetIds.length} · ~${formatCost(props.cost.totalSeconds)}`,
)

const detail = computed(() =>
  instant.value
    ? 'Every asset in this slice is already materialized.'
    : `${props.cost.cachedAssetIds.length} assets come from cache; ${props.cost.recomputeAssetIds.length} would recompute.`,
)
</script>
