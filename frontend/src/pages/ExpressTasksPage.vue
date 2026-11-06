<template>
  <div class="content">
    <div class="headings">
      <h1 class="main-title">Pick a Machine Learning Task</h1>
      <p class="sub-title">
        Select a task that aligns with your goals, or explore all options to find the best fit for
        your needs.
      </p>
    </div>
    <div class="body">
      <tasks-list label="Available tasks" :tasks="availableTasks" />
    </div>
  </div>
</template>

<script setup lang="ts">
import TasksList from '@/components/homepage-tasks/TasksList.vue'

import { availableTasks } from '@/constants/constants'
</script>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 36px;
}

.content {
  padding-top: 32px;
}

.headings {
  margin-bottom: 40px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

@media (max-width: 768px) {
  .body {
    gap: 15px;
  }
  .headings {
    margin-bottom: 20px;
  }
}
</style>
