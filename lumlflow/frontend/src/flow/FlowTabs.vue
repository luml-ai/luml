<script lang="ts">
import type { RouteLocationNormalizedLoaded } from 'vue-router'
import { flowPath } from './workbench/model/routes'

export interface FlowNavEntry {
  path: string
  label: string
}

export function flowNavEntries(route: RouteLocationNormalizedLoaded): FlowNavEntry[] {
  const entries: FlowNavEntry[] = []
  const openFlow = typeof route.params.flowId === 'string' ? route.params.flowId : ''
  if (openFlow) {
    entries.push(
      { path: flowPath(openFlow), label: 'Workbench' },
      { path: flowPath(openFlow, '/compare'), label: 'Compare' },
    )
  }
  if (import.meta.env.DEV) {
    entries.push({ path: '/flow/design', label: 'Design system' })
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

const route = useRoute()
const router = useRouter()

const entries = computed(() => flowNavEntries(route))

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
