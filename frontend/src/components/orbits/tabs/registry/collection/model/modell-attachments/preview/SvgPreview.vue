<template>
  <div class="svg-preview">
    <div class="svg-container">
      <object :data="contentUrl" type="image/svg+xml" class="svg-object" :aria-label="fileName">
        <img :src="contentUrl" :alt="fileName" class="svg-fallback" />
      </object>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  contentUrl: string
  fileName: string
}>()
</script>

<style scoped></style>
