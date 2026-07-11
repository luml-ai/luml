<template>
  <DatasetWrapper>
    <div v-if="!datasetsStore.manifest">
      <p class="message">No manifest found</p>
    </div>

    <div v-else-if="datasetsStore.manifest.variant === 'hf'">
      <p class="message">We currently don't support HuggingFace dataset variant</p>
    </div>

    <DatasetBody v-else></DatasetBody>
  </DatasetWrapper>
</template>

<script setup lang="ts">
import { useDatasetsStore } from '@/stores/datasets'
import DatasetWrapper from '@/components/datasets/DatasetWrapper.vue'
import DatasetBody from '@/components/datasets/DatasetBody.vue'

const datasetsStore = useDatasetsStore()
</script>

<style scoped>
.message {
  color: var(--p-text-muted-color);
}
</style>
