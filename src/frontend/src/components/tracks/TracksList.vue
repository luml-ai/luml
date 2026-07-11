<template>
  <VirtualScroller
    :items="list"
    :itemSize="126"
    lazy
    @lazy-load="$emit('lazy-load', $event)"
    class="border border-surface-200 dark:border-surface-700 rounded"
    style="height: calc(100vh - 300px); margin-bottom: -70px"
  >
    <template v-slot:item="{ item }">
      <div class="card-wrapper">
        <TrackCard
          :key="item.id"
          :date="item.updated_at ?? item.created_at"
          :type="item.artifact_type"
          :artifactsCount="item.total_entries"
          :id="item.id"
          :name="item.name"
          :description="item.description ?? ''"
          :stages="item.tags ?? []"
        />
      </div>
    </template>
  </VirtualScroller>
</template>

<script setup lang="ts">
import type { Track } from '@/lib/api/orbit-tracks/interfaces.js'
import TrackCard from './TrackCard.vue'
import { VirtualScroller, type VirtualScrollerLazyEvent } from 'primevue'

interface Props {
  list: Track[]
}

type Emits = {
  (e: 'lazy-load', event: VirtualScrollerLazyEvent): void
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.card-wrapper {
  margin-bottom: 24px;
}
</style>
