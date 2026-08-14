<template>
  <div class="overflow-x-auto">
    <table class="w-full border-collapse text-base">
      <thead>
        <tr class="text-left text-sm text-muted-color">
          <th class="py-1.5 pr-6 font-medium">asset</th>
          <th class="py-1.5 pr-6 font-medium">what</th>
          <th class="py-1.5 font-medium">lanes</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="difference in differences"
          :key="difference.slug + difference.what"
          class="border-t border-surface-200 dark:border-surface-700"
        >
          <td class="py-2 pr-6 align-top font-mono text-base">{{ difference.slug }}</td>
          <td class="py-2 pr-6 align-top">{{ difference.what }}</td>
          <td class="py-2 align-top">
            <span class="flex flex-wrap gap-x-3 gap-y-1">
              <BranchTag v-for="branch in difference.branches" :key="branch" :name="branch" />
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import type { ShapelessDifference } from '../../model/types'
import BranchTag from '../../ui/BranchTag.vue'

defineProps<{ differences: ShapelessDifference[] }>()
</script>
