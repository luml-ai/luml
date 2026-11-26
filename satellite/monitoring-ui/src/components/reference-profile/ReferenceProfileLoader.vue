<template>
  <div class="loader">
    <div class="tabs">
      <Skeleton width="80px" height="16px" />
      <Skeleton width="80px" height="16px" />
    </div>
    <div class="summary">
      <div v-for="index in SUMMARY_COUNT" :key="index" class="item">
        <Skeleton width="90px" height="14px" />
        <Skeleton width="70px" height="22px" />
      </div>
    </div>
    <Skeleton :height="contentHeight" />
  </div>
</template>

<script setup lang="ts">
import { Skeleton } from 'primevue'
import { REFERENCE_PROFILE_CONTENT_HEIGHT } from '@/constants/reference-profile'

const SUMMARY_COUNT = 5

const contentHeight = `${REFERENCE_PROFILE_CONTENT_HEIGHT}px`
</script>

<style scoped>
.loader {
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 20px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
}

.tabs {
  display: flex;
  gap: 36px;
  padding: 16px 18px 17px;
  border-bottom: 1px solid var(--p-content-border-color);
}

.summary {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px 24px;
}

.item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
</style>
