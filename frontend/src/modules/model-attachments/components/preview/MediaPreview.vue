<template>
  <div class="content-media" :class="`content-${props.type}`">
    <audio v-if="props.type === 'audio'" controls :src="props.contentUrl"></audio>
    <video v-else-if="props.type === 'video'" controls :src="props.contentUrl"></video>
  </div>
</template>

<script setup lang="ts">
import type { MediaPreviewProps } from '../../interfaces/interfaces'
const props = defineProps<MediaPreviewProps>()
</script>

<style scoped>
.content-media {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100%;
}

.content-audio audio {
  width: 100%;
  max-width: 600px;
}

.content-video video {
  width: 100%;
  max-width: 800px;
  max-height: 600px;
}
</style>
