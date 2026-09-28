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
}

const EXAMPLE_FLOW = 'churn.flow'

const pages: PageCard[] = [
  { title: 'Workspace', to: '/flow' },
  { title: 'Workbench · canvas', to: `/flow/${EXAMPLE_FLOW}` },
  { title: 'Workbench · notebook', to: `/flow/${EXAMPLE_FLOW}/notebook` },
  { title: 'Compare', to: `/flow/${EXAMPLE_FLOW}/compare` },
]
</script>
