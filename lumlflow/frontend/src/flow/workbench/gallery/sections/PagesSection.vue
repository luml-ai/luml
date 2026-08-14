<template>
  <div class="flex max-w-4xl flex-col gap-6">
    <div class="grid gap-6 sm:grid-cols-2">
      <div
        v-for="page in pages"
        :key="page.to"
        class="flex flex-col gap-4 rounded-lg border border-surface-200 bg-surface-0 p-5 dark:border-surface-700 dark:bg-surface-900"
      >
        <div class="flex items-center justify-between gap-3">
          <p class="text-base font-medium">{{ page.title }}</p>
          <RouterLink
            :to="page.to"
            class="inline-flex items-center gap-1.5 rounded-lg border border-surface-300 px-2.5 py-1 text-sm transition-colors hover:border-primary-400 hover:text-primary-600 dark:border-surface-600 dark:hover:border-primary-500 dark:hover:text-primary-400"
          >
            open
            <ArrowRight :size="14" />
          </RouterLink>
        </div>

        <div v-if="page.stateChips" class="flex flex-wrap gap-1.5">
          <RouterLink
            v-for="state in workbenchStates"
            :key="state"
            :to="`/flow/${FIXTURE_FLOW}?state=${state}`"
            class="rounded-lg border border-surface-200 px-1.5 py-0.5 font-mono text-sm text-muted-color transition-colors hover:border-primary-400 hover:text-primary-600 dark:border-surface-700 dark:hover:border-primary-500 dark:hover:text-primary-400"
          >
            {{ state }}
          </RouterLink>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'
import { ArrowRight } from 'lucide-vue-next'

interface PageCard {
  title: string
  to: string
  stateChips?: boolean
}

/** The gallery's stand-in document, so the fixture pages have an address. */
const FIXTURE_FLOW = 'churn.flow'

/** Explicit, so these specimens keep showing the fixture whether or not the tab is connected. */
const AS_FIXTURE = '?source=fixture'

const pages: PageCard[] = [
  { title: 'Workspace', to: '/flow' },
  { title: 'Workbench · canvas', to: `/flow/${FIXTURE_FLOW}${AS_FIXTURE}`, stateChips: true },
  { title: 'Workbench · notebook', to: `/flow/${FIXTURE_FLOW}/notebook${AS_FIXTURE}` },
  { title: 'Compare', to: `/flow/${FIXTURE_FLOW}/compare${AS_FIXTURE}` },
  { title: 'Reference · railroad', to: '/flow/railroad' },
]

const workbenchStates = [
  'running',
  'idle',
  'unpaired',
  'empty',
  'kernel-not-started',
  'not-running',
  'locked',
]
</script>
