<template>
  <div class="card">
    <div class="label">
      <Folders :size="24" color="var(--p-primary-color)" />
      <div class="name">{{ name }}</div>
    </div>
    <div class="id-row">
      <span class="id-text"> Id: </span>
      <UiId :id="id" />
    </div>
    <div class="info">
      <div class="info-item">
        <History :size="12" />
        <span>{{ updatedText }}</span>
      </div>
      <div class="info-item">
        <component
          v-if="COLLECTION_TYPE_CONFIG[type]"
          :is="COLLECTION_TYPE_CONFIG[type].icon"
          :size="12"
        />
        <span>{{ COLLECTION_TYPE_CONFIG[type]?.label ?? 'Unknown type' }}</span>
      </div>
      <div class="info-item">
        <Database :size="12" />
        <span>{{ totalArtifacts }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import { Database, Folders, History } from 'lucide-vue-next'
import { computed } from 'vue'
import { getLastUpdateText } from '@/helpers/helpers'
import { COLLECTION_TYPE_CONFIG } from './collection.const'
import UiId from '@/components/ui/UiId.vue'

interface Props {
  name: string
  id: string
  createdAt: string
  updatedAt: string | null
  type: OrbitCollectionTypeEnum
  totalArtifacts: number
}

const props = defineProps<Props>()

const updatedText = computed(() => {
  return getLastUpdateText(props.updatedAt || props.createdAt)
})
</script>

<style scoped>
.card {
  height: 107px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  padding: 16px;
  width: 100%;
  cursor: pointer;
  transition: background-color 0.3s;
}
.card:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 500;
  margin-bottom: 8px;
}
.id-row {
  font-size: 12px;
  display: flex;
  align-items: center;
  gap: 4px;
  margin-bottom: 8px;
}
.id-text {
  color: var(--p-text-muted-color);
}
.info {
  display: flex;
  gap: 12px;
}
.info-item {
  display: flex;
  align-items: center;
  font-size: 12px;
  gap: 4px;
  color: var(--p-text-muted-color);
}
</style>
