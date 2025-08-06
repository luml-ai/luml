<template>
  <iframe :src="url" class="iframe"></iframe>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

type Props = {
  url: string
}

defineProps<Props>()

onMounted(() => {})
</script>

<style scoped>
.iframe {
  width: 100%;
  height: calc(100vh - 310px);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}
</style>
