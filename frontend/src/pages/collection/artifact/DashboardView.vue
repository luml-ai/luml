<template>
  <div v-if="artifactsStore.currentArtifact" class="card">
    <ArtifactDetails :artifact="artifactsStore.currentArtifact" with-manifest />
  </div>
</template>

<script setup lang="ts">
import { useArtifactsStore } from '@/stores/artifacts'
import ArtifactDetails from '@/components/orbits/tabs/registry/collection/artifact/ArtifactDetails.vue'

const artifactsStore = useArtifactsStore()
</script>

<style scoped>
.card {
  padding: 20px;
  background-color: var(--p-card-background);
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--card-shadow);
}
</style>
