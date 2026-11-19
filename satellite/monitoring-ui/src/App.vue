<template>
  <main class="app" data-testid="monitoring-app">
    <h2 v-if="headerStore.title" class="title">{{ headerStore.title }}</h2>
    <MTabs />
    <MFilters />
    <MTabsContent />
    <Toast />
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { Toast } from 'primevue'
import MFilters from './components/filters/MFilters.vue'
import MTabs from './components/MTabs.vue'
import MTabsContent from './components/MTabsContent.vue'
import { useHeaderStore } from './store/header'

const headerStore = useHeaderStore()

onMounted(headerStore.loadHeader)
</script>

<style scoped>
.app {
  min-height: 100vh;
  padding: 16px;
}

.title {
  font-size: 24px;
  font-weight: 500;
  margin-bottom: 20px;
}
</style>
