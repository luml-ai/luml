<template>
  <VirtualScroller
    v-if="list.length > 0"
    :items="list"
    :itemSize="139"
    lazy
    @lazy-load="$emit('lazy-load', $event)"
    class="border border-surface-200 dark:border-surface-700 rounded"
    :style="{ height: height }"
  >
    <template v-slot:item="{ item }">
      <div class="card-wrapper">
        <ArtifactCard
          :key="item.id"
          :data="item"
          :collection-name="item.collection_name"
          :selected="selectedArtifact === item.id"
          :organization-id="organizationId"
          :orbit-id="orbitId"
          @add="$emit('add', item.id)"
        />
      </div>
    </template>
  </VirtualScroller>
  <div v-else class="empty-state">
    <p>No artifacts found</p>
  </div>
</template>

<script setup lang="ts">
import { type Artifact } from '@/lib/api/artifacts/interfaces'
import ArtifactCard from './ArtifactCard.vue'
import { VirtualScroller, type VirtualScrollerLazyEvent } from 'primevue'

interface Props {
  list: Artifact[]
  selectedArtifact: string
  organizationId: string
  orbitId: string
  height?: string
}

interface Emits {
  (e: 'lazy-load', event: VirtualScrollerLazyEvent): void
  (e: 'add', id: string): void
}

withDefaults(defineProps<Props>(), {
  height: '389px',
})

defineEmits<Emits>()
</script>

<style scoped>
.empty-state {
  text-align: center;
  padding: 40px;
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.card-wrapper {
  margin-bottom: 8px;
}

:deep(.p-virtualscroller-content) {
  max-width: 100%;
}
</style>
