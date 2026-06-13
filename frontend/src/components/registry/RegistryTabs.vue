<template>
  <Tabs :value="routeName">
    <TabList>
      <template v-for="tab in items" :key="tab.label">
        <Tab :value="tab.routeName" class="tab" @click="$router.push({ name: tab.routeName })">
          <component :is="tab.icon" :size="14" />
          <span>{{ tab.label }}</span>
        </Tab>
      </template>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { Folders, TrainTrack } from 'lucide-vue-next'
import { Tabs, TabList, Tab } from 'primevue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const items = [
  {
    label: 'Collections',
    routeName: 'orbit-collections',
    icon: Folders,
  },
  {
    label: 'Tracks',
    routeName: 'orbit-tracks',
    icon: TrainTrack,
  },
]

const routeName = computed(() => route.name as string)
</script>

<style scoped>
:deep(.p-tablist-tab-list) {
  border-left: none;
  border-top: none;
  border-right: none;
}

.tab {
  border: none;
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
