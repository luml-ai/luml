<template>
  <div class="content-media" :class="`content-${type}`">
    <audio v-if="type === 'audio' && contentUrl" controls :src="contentUrl"></audio>
    <video v-if="type === 'video' && contentUrl" controls :src="contentUrl"></video>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  type: 'audio' | 'video'
  contentUrl: string
}>()
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
