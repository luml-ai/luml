<template>
  <div class="content-html">
    <iframe v-if="contentUrl" :src="contentUrl" sandbox="allow-same-origin"></iframe>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  contentUrl: string
}>()
</script>

<style scoped>
.content-html {
  flex: 1;
  height: 100%;
}

.content-html iframe {
  width: 100%;
  height: 100%;
  min-height: 600px;
  border: none;
}
</style>
