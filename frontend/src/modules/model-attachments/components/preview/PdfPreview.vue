<template>
  <div class="content-pdf">
    <iframe :src="props.contentUrl" frameborder="0"></iframe>
  </div>
</template>

<script setup lang="ts">
import type { PdfPreviewProps } from '../../interfaces/interfaces'

const props = defineProps<PdfPreviewProps>()
</script>

<style scoped>
.content-pdf {
  flex: 1;
  height: 100%;
}

.content-pdf iframe {
  width: 100%;
  height: 100%;
}
</style>
