<template>
  <div class="flex flex-col flex-auto">
    <Skeleton v-if="loading" height="calc(100vh - 260px)" />
    <div
      v-else-if="error"
      class="text-center h-[calc(100vh-260px)] flex items-center justify-center"
    >
      <p class="text-muted-color">{{ error }}</p>
    </div>
    <ModelAttachments v-else-if="provider" :provider="provider" class="attachments" />
  </div>
</template>

<script setup lang="ts">
import { ModelAttachments } from '@luml/attachments'
import { onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import { useAttachmentsProvider } from '@/composables/useAttachmentsProvider'
import { Skeleton } from 'primevue'

const route = useRoute()
const { provider, loading, error, init } = useAttachmentsProvider(
  route.params.experimentId as string,
)

onBeforeMount(() => {
  init()
})
</script>

<style scoped>
.attachments {
  height: calc(100vh - 260px);
}
</style>
