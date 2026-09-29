<template>
  <div class="page-header">
    <ChartSpline :size="20" class="page-header__icon" />
    <router-link :to="{ name: 'orbit-flow' }" class="page-header__back">Flow</router-link>
    <span>/</span>
    <h1 class="page-header__title">{{ route.params.sessionId }}</h1>
  </div>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
import { ChartSpline } from 'lucide-vue-next'

const route = useRoute()
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 25px;
  padding-top: 37px;
}

.page-header__icon {
  flex-shrink: 0;
  color: var(--p-primary-color);
}

.page-header__back {
  color: var(--p-text-muted-color);
  text-decoration: none;
}

.page-header__title {
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
}
</style>
