<template>
  <div class="preview-table flex min-w-0 flex-col gap-2.5 text-base">
    <div class="overflow-auto" :class="bodyMaxClass(density)">
      <DataTable :value="rows" size="small" striped-rows>
        <!-- dtype rides under the header, as in the frame renderer. -->
        <Column v-for="(column, index) in preview.schema" :key="column.name" :field="String(index)">
          <template #header>
            <span class="leading-tight">
              <span class="font-medium whitespace-nowrap">{{ column.name }}</span>
              <span class="block text-sm text-muted-color font-normal">{{ column.dtype }}</span>
            </span>
          </template>
          <template #body="{ data }">
            <span class="whitespace-nowrap tabular-nums">{{ data[index] ?? '—' }}</span>
          </template>
        </Column>
      </DataTable>
    </div>

    <p class="text-sm text-muted-color">
      {{ preview.totalRows.toLocaleString() }} rows · {{ formatBytes(preview.sizeBytes) }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Column, DataTable } from 'primevue'
import { formatBytes } from '../model/format'
import type { DatasetPreview } from '../model/types'
import { bodyMaxClass, type RenderDensity } from './shared'

const props = defineProps<{
  preview: DatasetPreview
  density?: RenderDensity
}>()

const rows = computed(() => props.preview.head.map((row) => ({ ...row })))
</script>
