<template>
  <div class="flex h-full flex-col">
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

const route = useRoute()

const onWorkbench = computed(
  () => Boolean(route.params.flowId) && !route.path.endsWith('/compare'),
)

const showTabs = computed(() => !onWorkbench.value && flowNavEntries(route).length > 0)
</script>
