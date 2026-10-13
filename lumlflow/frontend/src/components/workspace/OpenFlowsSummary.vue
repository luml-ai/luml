<template>
  <template v-if="summary">
    <button type="button" class="summary" aria-haspopup="dialog" @click="popover?.toggle($event)">
      {{ summary }}
    </button>
    <Popover ref="popover" :pt="POPOVER_PT">
      <ul class="open-flows">
        <li v-for="row in rows" :key="row.path">
          <RouterLink
            :to="{ name: ROUTE_NAMES.WORKSPACE_FLOW, query: { directory: row.path } }"
            class="open-flow"
          >
            <FlowStateMarker
              :kernel="row.kernel"
              :label="row.active_runs"
              :agents="row.leased_sessions"
              :last-activity="row.last_activity"
            />
            <span class="open-flow-name">{{ row.name }}</span>
            <span v-if="row.directory" class="open-flow-directory">{{ row.directory }}</span>
          </RouterLink>
        </li>
      </ul>
    </Popover>
  </template>
</template>

<script setup lang="ts">
import type { OpenFlow } from '@/api/slices/workspace/workspace.interface'
import type { PopoverPassThroughOptions } from 'primevue'
import { Popover } from 'primevue'
import { computed, useTemplateRef } from 'vue'
import { useWorkspaceStore } from '@/store/workspace'
import { baseName, parentDirectory } from '@/helpers/path'
import { ROUTE_NAMES } from '@/router/router.const'
import FlowStateMarker from '@/components/workspace/FlowStateMarker.vue'

const POPOVER_PT: PopoverPassThroughOptions = {
  content: { class: 'p-2' },
}

const workspaceStore = useWorkspaceStore()
const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')

const summary = computed(() => {
  const totals = workspaceStore.openFlowsTotals
  if (totals.open_flows === 0) return null
  const open = `${totals.open_flows} open`
  return totals.running_kernels ? `${open} · ${totals.running_kernels} running` : open
})

// Inside flows name their folder relative to the listing; others their absolute directory.
function directoryOf(flow: OpenFlow): string | null {
  if (flow.inside) return flow.relative_path ? parentDirectory(flow.relative_path) : null
  return parentDirectory(flow.path)
}

const rows = computed(() =>
  [...workspaceStore.openFlows]
    .sort((a, b) => a.path.localeCompare(b.path))
    .map((flow) => ({ ...flow, name: baseName(flow.path), directory: directoryOf(flow) })),
)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.summary {
  @apply shrink-0 text-sm text-muted-color cursor-pointer hover:text-primary transition-colors;
}
.open-flows {
  @apply flex flex-col min-w-56 max-w-120;
}
.open-flow {
  @apply flex items-center gap-2 px-2 py-1.5 rounded-md text-sm transition-colors;
}
.open-flow:hover {
  background-color: var(--p-list-option-focus-background);
}
.open-flow-name {
  @apply shrink-0;
}
.open-flow-directory {
  @apply text-muted-color truncate;
}
</style>
