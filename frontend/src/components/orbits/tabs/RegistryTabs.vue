<template>
  <div class="tabs">
    <button
      class="tab"
      :class="{ active: activeTab === 'collections' }"
      @click="switchTab('orbit-registry')"
    >
      <Folders :size="14" />
      <span>Collections</span>
    </button>
    <button
      class="tab"
      :class="{ active: activeTab === 'tracks' }"
      @click="switchTab('orbit-tracks')"
    >
      <TrainTrack :size="14" />
      <span>Tracks</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Folders, TrainTrack } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const activeTab = computed(() => (route.name === 'orbit-tracks' ? 'tracks' : 'collections'))

function switchTab(targetRoute: 'orbit-registry' | 'orbit-tracks') {
  if (route.name === targetRoute) return
  router.push({ name: targetRoute, params: route.params })
}
</script>

<style scoped>
.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--p-divider-border-color);
  margin-bottom: 25px;
}

.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  color: var(--tabs-tab-color);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition:
    color 0.2s,
    border-color 0.2s;
  margin-bottom: -1px;
  background: transparent;
  border-left: none;
  border-top: none;
  border-right: none;
}

.tab.active {
  color: var(--p-primary-color);
  border-bottom-color: var(--p-primary-color);
}
</style>
