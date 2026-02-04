<template>
  <div class="fixed w-full h-full overflow-hidden flex flex-col p-4 pt-0">
    <MainHeader class="mb-6 -mx-4" />
    <main class="flex-1 overflow-y-auto">
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import MainHeader from '@/components/layout/header/MainHeader.vue'
</script>

<style scoped></style>
