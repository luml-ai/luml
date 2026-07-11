<template>
  <RegistryHeader />

  <RegistryTabs class="tabs" />

  <RouterView />
</template>

<script setup lang="ts">
import { onUnmounted } from 'vue'
import { useCollectionsStore } from '@/stores/collections'
import RegistryHeader from '@/components/registry/RegistryHeader.vue'
import RegistryTabs from '@/components/registry/RegistryTabs.vue'

const collectionsStore = useCollectionsStore()

onUnmounted(() => {
  collectionsStore.reset()
})
</script>

<style scoped>
.tabs {
  margin-bottom: 20px;
}
</style>
