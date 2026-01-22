<template>
  <VirtualScroller
    :items="list"
    :itemSize="171"
    lazy
    @lazy-load="$emit('lazy-load', $event)"
    class="border border-surface-200 dark:border-surface-700 rounded"
    style="height: calc(100vh - 300px); margin-bottom: -70px"
  >
    <template v-slot:item="{ item }">
      <div class="card-wrapper">
        <CollectionCard :edit-available="editAvailable" :data="item"></CollectionCard>
      </div>
    </template>
  </VirtualScroller>
</template>

<script setup lang="ts">
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import { VirtualScroller, type VirtualScrollerLazyEvent } from 'primevue'
import { computed } from 'vue'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import CollectionCard from './CollectionCard.vue'

type Props = {
  list: OrbitCollection[]
}

type Emits = {
  (e: 'lazy-load', event: VirtualScrollerLazyEvent): void
}

defineProps<Props>()
defineEmits<Emits>()

const orbitsStore = useOrbitsStore()

const editAvailable = computed(() => {
  return !!orbitsStore.getCurrentOrbitPermissions?.collection.includes(PermissionEnum.update)
})
</script>

<style scoped>
.no-results {
  text-align: center;
  padding: 40px;
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.card-wrapper {
  margin-bottom: 24px;
}
</style>
