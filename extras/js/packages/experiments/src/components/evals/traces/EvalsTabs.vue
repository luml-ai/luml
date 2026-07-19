<template>
  <Tabs :value="currentId" @update:value="onValueUpdate">
    <TabList>
      <template v-for="id in ids" :key="id">
        <Tab :value="id">
          <div class="tab-content">{{ id }}</div>
        </Tab>
      </template>
    </TabList>
  </Tabs>
</template>

<script setup lang="ts">
import { TabList, Tabs, Tab } from 'primevue'

interface Props {
  ids: string[]
  currentId: string
}

interface Emits {
  (e: 'update:currentId', value: string): void
}

defineProps<Props>()

const emit = defineEmits<Emits>()

function onValueUpdate(value: string | number) {
  emit('update:currentId', String(value))
}
</script>

<style scoped>
.tab-content {
  max-width: 70px;
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.p-tablist {
  background-color: transparent;
}

:deep(.p-tablist-tab-list) {
  border-left: none;
  border-top: none;
  border-right: none;
}

:deep(.p-tab) {
  border: none;
}
</style>
