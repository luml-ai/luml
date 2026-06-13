<template>
  <div class="mb-5">
    <h3 class="text-lg mb-4">Logged models ({{ formattedModels.length }})</h3>
    <Card>
      <template #content>
        <DataTable
          :value="formattedModels"
          table-class="table-fixed"
          scrollable
          scrollHeight="200px"
          :virtualScrollerOptions="formattedModels.length > 10 ? { itemSize: 43 } : undefined"
        >
          <template #empty>
            <div class="flex justify-center items-center h-full">
              <span>No models found</span>
            </div>
          </template>
          <Column field="name" header="Model name">
            <template #body="slotProps">
              <button
                class="flex items-center gap-2 hover:underline cursor-pointer"
                @click="onModelClick(slotProps.data.id)"
              >
                <CircuitBoardIcon :size="14" color="var(--p-primary-color)" />
                <span>{{ slotProps.data.name }}</span>
              </button>
            </template>
          </Column>
          <Column field="size" header="Size"></Column>
          <Column field="created_at" header="Creation time"></Column>
        </DataTable>
      </template>
    </Card>
  </div>
</template>

<script setup lang="ts">
import type { Model } from '@/store/experiments/experiments.interface'
import { Card, DataTable, Column } from 'primevue'
import { CircuitBoardIcon } from 'lucide-vue-next'
import { computed } from 'vue'
import { getSizeText } from '@/helpers/string'
import { dateToText } from '@/helpers/date'
import { useModelCardStore } from '@/store/model-card'

interface Props {
  groupId: string
  experimentId: string
  models: Model[]
}

const props = defineProps<Props>()

const modelCardStore = useModelCardStore()

const formattedModels = computed(() =>
  props.models.map((model) => ({
    ...model,
    size: getSizeText(model.size || 0),
    created_at: dateToText(model.created_at),
  })),
)

function onModelClick(modelId: string) {
  modelCardStore.showModelCard(modelId)
}
</script>

<style scoped></style>
