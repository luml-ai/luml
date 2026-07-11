<template>
  <div
    class="page-loader"
    :style="{
      height: `calc(100vh - ${headerSizes.height}px)`,
    }"
  >
    <ProgressSpinner></ProgressSpinner>
  </div>
</template>

<script setup lang="ts">
import { useLayout } from '@/hooks/useLayout'
import { ProgressSpinner } from 'primevue'

const { headerSizes } = useLayout()
</script>

<style scoped>
.page-loader {
  width: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
