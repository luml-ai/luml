<template>
  <div class="list">
    <OrbitCard
      v-if="orbits.length === 0"
      :manage-available="createAvailable"
      type="create"
      @create-new="$emit('createNew')"
    ></OrbitCard>
    <OrbitCard
      v-for="orbit in orbits"
      :manage-available="createAvailable"
      :key="orbit.id"
      :data="orbit"
      type="default"
    ></OrbitCard>
  </div>
</template>

<script setup lang="ts">
import type { Orbit } from '@/lib/api/api.interfaces'
import OrbitCard from './card/OrbitCard.vue'

type Props = {
  orbits: Orbit[]
  createAvailable: boolean
}

type Emits = {
  createNew: []
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
</style>
