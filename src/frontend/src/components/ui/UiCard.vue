<template>
  <div class="card">
    <header class="card__header">
      <slot name="header-left">
        <h3 class="card__title">{{ title }}</h3>
      </slot>
      <slot name="header-right"></slot>
    </header>
    <div class="card__body">
      <slot name="default"></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
type Props = {
  title?: string
}

defineProps<Props>()
</script>

<style scoped>
.card {
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  border-radius: 8px;
  padding: 20px;
}
.card__header {
  margin-bottom: 24px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.card__title {
  font-size: 20px;
}
.card__body {
}
</style>
