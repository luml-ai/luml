<template>
  <div class="flex flex-col gap-2">
    <p class="text-sm text-muted-color">same code, different inputs</p>
    <div class="overflow-x-auto">
      <div
        class="grid items-center gap-x-5 gap-y-0"
        :style="{
          gridTemplateColumns: `max-content repeat(${branchOrder.length}, minmax(7rem, max-content))`,
        }"
      >
        <span />
        <span v-for="branch in branchOrder" :key="branch" class="pb-1.5">
          <BranchTag :name="branch" />
        </span>

        <template v-for="row in rows" :key="row.slug + (row.output ?? '')">
          <span
            class="border-t border-surface-200 py-2 pr-2 font-mono text-base dark:border-surface-700"
          >
            {{ row.slug }}<span v-if="row.output" class="text-muted-color">.{{ row.output }}</span>
          </span>
          <span
            v-for="branch in branchOrder"
            :key="branch"
            class="border-t border-surface-200 py-2 dark:border-surface-700"
          >
            <Tag
              v-if="row.byBranch[branch]"
              :severity="severityFor(row.byBranch[branch].state)"
              :value="row.byBranch[branch].label"
              :pt="CHIP_PT"
              :class="row.byBranch[branch].state === 'missing' ? 'opacity-60' : ''"
            />
            <span v-else class="text-sm text-muted-color">—</span>
          </span>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import type { MaterializationRow } from '../../model/types'
import BranchTag from '../../ui/BranchTag.vue'

const props = defineProps<{ rows: MaterializationRow[] }>()

const branchOrder = computed(() => {
  const branches: string[] = []
  for (const row of props.rows)
    for (const branch of Object.keys(row.byBranch))
      if (!branches.includes(branch)) branches.push(branch)
  return branches
})

const CHIP_PT = { root: { class: 'px-2 py-0 text-sm font-normal tabular-nums' } }

const SEVERITIES: Record<string, 'secondary' | 'success' | 'danger'> = {
  same: 'secondary',
  better: 'success',
  worse: 'danger',
  missing: 'secondary',
}

function severityFor(state: string): 'secondary' | 'success' | 'danger' {
  return SEVERITIES[state] ?? 'secondary'
}
</script>
