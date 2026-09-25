<template>
  <div class="flex h-full flex-col">
    <!--
      The flow's own strip, and only where nothing else carries it: on the
      workbench the tabs ride in `WorkbenchTopBar`, which already names the open
      flow — a second chrome bar there was 60 px of nothing on every screen.
    -->
    <header v-if="showTabs" class="border-b border-surface-200 dark:border-surface-700">
      <FlowTabs class="min-w-0 flex-1" />
    </header>

    <div class="min-h-0 flex-1 overflow-auto" :class="showTabs ? 'pt-3' : ''">
      <RouterView :key="route.fullPath" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import FlowTabs, { flowNavEntries } from './FlowTabs.vue'

/**
 * The flow surface's shell. Branding and the top-level Experiments/Workspace
 * switch belong to `MainHeader.vue` above it; the open flow's own views belong
 * to whichever bar is already naming that flow.
 */

const route = useRoute()

/**
 * The workbench carries the tabs itself, in the bar that names the flow. Read
 * off the path rather than the route name so the rule holds wherever the
 * component is mounted: a flow is open and this is not its comparison.
 */
const onWorkbench = computed(
  () => Boolean(route.params.flowId) && !route.path.endsWith('/compare'),
)

const showTabs = computed(() => !onWorkbench.value && flowNavEntries(route).length > 0)
</script>
