<template>
  <ImagePreview :content-url="props.contentUrl" :file-name="props.fileName" />
</template>

<script setup lang="ts">
import type { SvgPreviewProps } from '../../interfaces/interfaces'
import ImagePreview from './ImagePreview.vue'

const props = defineProps<SvgPreviewProps>()
</script>

<style scoped></style>
