<template>
  <div class="svg-preview">
    <div class="svg-container">
      <object
        :data="props.contentUrl"
        type="image/svg+xml"
        class="svg-object"
        :aria-label="props.fileName"
      >
        <img :src="props.contentUrl" :alt="props.fileName" class="svg-fallback" />
      </object>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SvgPreviewProps } from '../../interfaces/interfaces'

const props = defineProps<SvgPreviewProps>()
</script>

<style scoped></style>
