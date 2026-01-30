<template>
  <div class="app">
    <div class="app-header">
      <h1 class="app-title">Luml Attachments Demo</h1>
      <input type="file" @change="handleFileChange" />
      <Button label="Toggle Theme" @click="toggleTheme" />
    </div>
    <ModelAttachments v-if="provider" :provider="provider" class="attachments" />
  </div>
</template>

<script setup lang="ts">
import type { ModelAttachmentsProvider } from '@/interfaces/interfaces'
import { ref } from 'vue'
import { FnnxService } from './lib/fnnx/FnnxService'
import { FileProvider } from './models/FileProvider'
import { Button } from 'primevue'
import ModelAttachments from '@/ModelAttachments.vue'

const provider = ref<ModelAttachmentsProvider | null>(null)

const theme = ref<'light' | 'dark'>('light')

const handleFileChange = async (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) {
    provider.value = null
    return
  }
  try {
    const model = await FnnxService.createModelFromFile(file)
    const files = (model as any).modelFiles
    const index = FnnxService.findAttachmentsIndex(files)
    const tar = FnnxService.findAttachmentsTar(files)
    if (index && tar) {
      provider.value = createProvider(index, tar)
    }
  } catch (error) {
    console.error(error)
  }
}

function createProvider(index: Uint8Array, tar: Uint8Array) {
  return new FileProvider(index, tar)
}

function toggleTheme() {
  theme.value = theme.value === 'light' ? 'dark' : 'light'
  document.documentElement.dataset.theme = theme.value
}
</script>

<style scoped>
.app {
  padding: 15px;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.app-title {
  margin-bottom: 20px;
}

.attachments {
  height: calc(100vh - 108px);
}
</style>
