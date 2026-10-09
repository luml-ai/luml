<template>
  <RouterLink class="card" :to="to">
    <div class="left">
      <div class="header">
        <div class="label">
          {{ title }}
        </div>
        <div class="id-container">
          <Tag severity="secondary">
            <UiId :id="id" class="id"></UiId>
          </Tag>
        </div>
        <Button
          v-if="editAvailable"
          severity="secondary"
          variant="text"
          @click.prevent.stop="emits('edit-click')"
        >
          <template #icon>
            <Bolt :size="14" />
          </template>
        </Button>
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
      <div v-if="description" class="description">
        {{ description }}
      </div>
      <UiTagsRow :tags="tags" />
    </div>
  </RouterLink>
</template>

<script setup lang="ts">
import type { RouteLocationRaw } from 'vue-router'
import type { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import { Button, Tag } from 'primevue'
import { Bolt, Database, History } from 'lucide-vue-next'
import { COLLECTION_TYPE_CONFIG } from '../orbits/tabs/registry/collection.const'
import { computed } from 'vue'
import { getLastUpdateText } from '@/helpers/helpers'
import UiId from './UiId.vue'
import UiTagsRow from './UiTagsRow.vue'

type Props = {
  title: string
  id: string
  editAvailable: boolean
  createdAt: string | Date
  updatedAt: string | Date | null
  type: OrbitCollectionTypeEnum
  totalArtifacts: number
  description: string
  tags: string[]
  to: RouteLocationRaw
}

type Emits = {
  'edit-click': []
}

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const updatedText = computed(() => {
  return getLastUpdateText(props.updatedAt || props.createdAt)
})
</script>

<style scoped>
.card {
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  padding: 6px 16px 6px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.3s;
  height: 136px;
  width: calc(100vw - 379px);
  display: block;
  color: inherit;
  text-decoration: none;
}
.card:hover {
  background-color: var(--p-autocomplete-chip-focus-background);
}
.header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
.label {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.info {
  display: flex;
  gap: 12px;
  margin-bottom: 8px;
}
.info-item {
  display: flex;
  align-items: center;
  font-size: 12px;
  gap: 4px;
  color: var(--p-text-muted-color);
}
.id-container {
  flex: 1 0 auto;
}
.id {
  color: var(--p-text-color);
}
.description {
  font-size: 12px;
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-bottom: 16px;
}

@media (max-width: 768px) {
  .card {
    width: calc(100vw - 30px);
  }
}
</style>
