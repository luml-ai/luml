<template>
  <div class="content-pdf">
    <iframe v-if="contentUrl" :src="contentUrl" frameborder="0"></iframe>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  contentUrl: string
}>()
</script>

<style scoped>
.content-pdf {
  flex: 1;
  height: 100%;
  min-height: 600px;
}

.content-pdf iframe {
  width: 100%;
  height: 100%;
  min-height: 600px;
}
</style>
