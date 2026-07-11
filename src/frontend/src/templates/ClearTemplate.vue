<template>
  <div class="wrapper">
    <LayoutHeader class="header" :is-actives-visible="false" />
    <main class="page">
      <slot />
    </main>
  </div>
</template>

<script setup lang="ts">
import LayoutHeader from '@/components/layout/LayoutHeader.vue'
</script>

<style scoped>
.header {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  z-index: 100;
}

.page {
  min-height: 100svh;
  padding: 100px 16px 60px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

@media (max-width: 768px) {
  .page {
    padding: 80px 15px 15px;
  }
}
</style>
