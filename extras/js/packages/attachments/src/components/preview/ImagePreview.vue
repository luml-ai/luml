<template>
  <div class="content-image">
    <img :src="props.contentUrl" :alt="props.fileName" />
  </div>
</template>

<script setup lang="ts">
import type { ImagePreviewProps } from '../../interfaces/interfaces'

const props = defineProps<ImagePreviewProps>()
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
