<template>
  <div>
    <h1 class="text-2xl font-medium mb-2.5">Welcome to LumlFlow</h1>
    <HomeTabs class="mb-6" />
    <router-view />
  </div>
</template>

<script setup lang="ts">
import HomeTabs from '@/components/tabs/HomeTabs.vue'
</script>

<style scoped></style>
