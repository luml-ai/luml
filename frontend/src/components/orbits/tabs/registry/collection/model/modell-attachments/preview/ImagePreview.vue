<template>
  <div class="content-image">
    <img :src="contentUrl" :alt="fileName" />
  </div>
</template>

<script setup lang="ts">
defineProps<{
  contentUrl: string
  fileName: string
}>()
</script>

<style scoped>
.content-image {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  height: 100%;
}

.content-image img {
  max-width: 100%;
  max-height: 100%;
  object-fit: contain;
}
</style>
