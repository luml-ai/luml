<template>
  <div class="wrapper">
    <h2 class="sub-title">{{ label }}</h2>
    <div class="items">
      <tasks-list-item v-for="task in tasks" :task="task" :key="task.id" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TaskList } from './interfaces'

import TasksListItem from './TasksListItem.vue'

defineProps<TaskList>()
</script>

<style scoped>
.items {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 24px;
}
.sub-title {
  font-size: 20px;
  font-weight: 500;
  margin-bottom: 24px;
}

@media (max-width: 1920px) {
  .items {
    grid-template-columns: repeat(3, 1fr);
  }
}

@media (max-width: 1440px) {
  .items {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 968px) {
  .items {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .items {
    gap: 15px;
  }
  .sub-title {
    margin-bottom: 10px;
  }
}
</style>
