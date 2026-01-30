<template>
  <div class="scores">
    <div v-for="score in scores" :key="score.name" class="score">
      <span class="score-name">{{ score.name }}</span>
      <span>{{ score.value.toFixed(9) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
type Props = {
  scores: { name: string; value: number }[]
}

defineProps<Props>()
</script>

<style scoped>
.scores {
  display: flex;
  flex-wrap: wrap;
  column-gap: 12px;
  row-gap: 8px;
}
.score {
  display: flex;
  white-space: nowrap;
  padding: 4px 8px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  display: flex;
  gap: 4px;
  font-size: 12px;
  font-weight: 500;
}
.score-name {
  color: var(--p-text-muted-color);
}
</style>
