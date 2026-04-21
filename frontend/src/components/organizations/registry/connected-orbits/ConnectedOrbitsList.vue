<template>
  <div class="content">
    <div class="label">Connected Orbits</div>
    <div class="list">
      <ConnectedOrbitsListItem v-for="orbit in orbits" :key="orbit.id" :orbit="orbit" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Orbit } from '@/lib/api/api.interfaces'
import ConnectedOrbitsListItem from './ConnectedOrbitsListItem.vue'

interface Props {
  orbits: Pick<Orbit, 'id' | 'name'>[]
}

defineProps<Props>()
</script>

<style scoped>
.content {
  padding: 20px 0;
  border-top: 1px solid var(--p-divider-border-color);
}
.label {
  font-weight: 500;
  margin-bottom: 8px;
}
.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
</style>
