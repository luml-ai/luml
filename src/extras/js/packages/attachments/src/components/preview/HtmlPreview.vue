<template>
  <div class="content-html">
    <iframe :src="props.contentUrl" sandbox="allow-same-origin"></iframe>
  </div>
</template>

<script setup lang="ts">
import type { HtmlPreviewProps } from '../../interfaces/interfaces'

const props = defineProps<HtmlPreviewProps>()
</script>

<style scoped>
.content-html {
  flex: 1;
  height: 100%;
  overflow: hidden;
}

.content-html iframe {
  width: 100%;
  height: 100%;
  min-height: 0;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}
</style>
