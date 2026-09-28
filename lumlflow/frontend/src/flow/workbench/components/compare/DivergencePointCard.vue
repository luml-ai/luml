<template>
  <div
    class="rounded-lg border border-surface-200 bg-surface-0 dark:border-surface-700 dark:bg-surface-900"
  >
    <div
      class="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-surface-200 px-4 py-2.5 dark:border-surface-700"
    >
      <Split :size="14" class="text-muted-color" />
      <span class="font-mono text-base font-medium">{{ divergence.slug }}</span>
      <span class="text-sm text-muted-color">definition divergence</span>
    </div>

    <div class="grid gap-3 p-4" style="grid-template-columns: repeat(auto-fit, minmax(230px, 1fr))">
      <div
        v-for="(side, index) in divergence.sides"
        :key="index"
        class="flex flex-col gap-2.5 rounded-lg border border-surface-200 p-3 dark:border-surface-700"
      >
        <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
          <BranchTag v-for="branch in side.branches" :key="branch" :name="branch" />
          <span class="ml-auto font-mono text-sm text-muted-color">{{ side.version }}</span>
        </div>

        <div class="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-0.5 text-sm">
          <template v-for="key in paramKeys" :key="key">
            <span
              class="font-mono"
              :class="differingKeys.has(key) ? 'text-(--p-message-warn-color)' : 'text-muted-color'"
            >
              {{ key }}
            </span>
            <span
              class="rounded-lg px-1 font-mono tabular-nums"
              :class="
                differingKeys.has(key)
                  ? 'bg-(--p-message-warn-background) font-medium text-(--p-message-warn-color)'
                  : ''
              "
            >
              {{ paramText(side.params[key]) }}
            </span>
          </template>
        </div>

        <pre
          class="overflow-x-auto rounded-lg bg-surface-50 p-2 font-mono text-sm leading-relaxed text-surface-700 dark:bg-surface-800 dark:text-surface-300"
          >{{ side.sourceExcerpt }}</pre
        >
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Split } from 'lucide-vue-next'
import type { DefinitionDivergence } from '../../model/types'
import type { ParamValue } from '../../model/types'
import BranchTag from '../../ui/BranchTag.vue'

const props = defineProps<{ divergence: DefinitionDivergence }>()

const paramKeys = computed(() => {
  const keys: string[] = []
  for (const side of props.divergence.sides)
    for (const key of Object.keys(side.params)) if (!keys.includes(key)) keys.push(key)
  return keys
})

const differingKeys = computed(() => {
  const differing = new Set<string>()
  for (const key of paramKeys.value) {
    const values = props.divergence.sides.map((side) => JSON.stringify(side.params[key]))
    if (new Set(values).size > 1) differing.add(key)
  }
  return differing
})

function paramText(value: ParamValue | undefined): string {
  if (value === undefined) return '—'
  return typeof value === 'string' ? value : JSON.stringify(value)
}
</script>
