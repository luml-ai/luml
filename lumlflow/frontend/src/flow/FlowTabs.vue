<script lang="ts">
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { flowPath } from './workbench/model/routes'

export interface FlowNavEntry {
  path: string
  label: string
}

/**
 * The views a flow has, plus the development surfaces. Workspace is not here —
 * `MainHeader` already carries it, and a fact belongs to one place on a screen.
 */
export function flowNavEntries(route: RouteLocationNormalizedLoaded): FlowNavEntry[] {
  const entries: FlowNavEntry[] = []
  // A flow's views are the flow's — there is no workbench without one open.
  const openFlow = typeof route.params.flowId === 'string' ? route.params.flowId : ''
  if (openFlow) {
    entries.push(
      { path: flowPath(openFlow), label: 'Workbench' },
      { path: flowPath(openFlow, '/compare'), label: 'Compare' },
    )
  }
  // The gallery and the superseded concept prototype are development surfaces:
  // the routes stay (tests mount them), the tabs do not ship.
  if (import.meta.env.DEV) {
    entries.push(
      { path: '/flow/design', label: 'Design system' },
      { path: '/flow/railroad', label: 'Railroad' },
    )
  }
  return entries
}

const TABLIST_PT = {
  root: { class: 'bg-transparent!' },
  tabList: { class: 'bg-transparent!', style: 'border: none' },
}
</script>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Tab, TabList, Tabs } from 'primevue'

/**
 * One tab idiom for the whole app: the same `Tabs`/`TabList`/`Tab` the
 * experiment details use, driven by the route rather than by local state.
 *
 * Each tab is a real link, so a view of a flow can be opened in a new tab and
 * pasted to somebody — a `role="tab"` button would have taken that away.
 */
const route = useRoute()
const router = useRouter()

const entries = computed(() => flowNavEntries(route))

// Longest match wins: every entry sits under `/flow`, and a flow's compare view
// is not also its canvas.
const current = computed(() => {
  const matched = entries.value
    .map((entry) => entry.path)
    .filter((path) => route.path === path || route.path.startsWith(`${path}/`))
  return matched.length ? matched.reduce((a, b) => (b.length > a.length ? b : a)) : ''
})

function go(path: string): void {
  if (path !== route.path) void router.push(path)
}
</script>

<template>
  <Tabs v-if="entries.length" :value="current" class="bg-transparent!">
    <TabList :pt="TABLIST_PT">
      <Tab
        v-for="entry in entries"
        :key="entry.path"
        :value="entry.path"
        as="a"
        :href="entry.path"
        class="tab"
        @click.prevent="go(entry.path)"
      >
        {{ entry.label }}
      </Tab>
    </TabList>
  </Tabs>
</template>

<style scoped>
.tab {
  border-inline: none;
  border-top: none;
  padding: 0.5rem 0.75rem;
  background: transparent !important;
}
</style>
