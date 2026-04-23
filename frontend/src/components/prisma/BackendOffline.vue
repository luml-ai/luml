<script setup lang="ts">
import { ref } from 'vue'
import { Button, InputText } from 'primevue'
import { WifiOff } from 'lucide-vue-next'
import { api } from '@/lib/api'
import { getStoredBackendUrl } from '@/lib/api/prisma'

const props = withDefaults(defineProps<{ versionMismatch?: boolean }>(), {
  versionMismatch: false,
})

const emit = defineEmits<{ retry: [] }>()

const retrying = ref(false)
const backendUrl = ref(getStoredBackendUrl())

async function onRetry() {
  retrying.value = true
  api.dataAgent.setBackendUrl(backendUrl.value)
  emit('retry')
  setTimeout(() => {
    retrying.value = false
  }, 1000)
}
</script>

<template>
  <div class="offline-container">
    <div class="offline-card">
      <WifiOff :size="48" class="offline-icon" />

      <template v-if="props.versionMismatch">
        <h3 class="offline-title">Prisma engine version mismatch</h3>
        <p class="offline-hint">
          The Prisma engine version is incompatible. Please update and restart.
        </p>
      </template>
      <template v-else>
        <h3 class="offline-title">Prisma engine is not running</h3>
        <p class="offline-hint">
          Prisma orchestrates coding agents to perform long-horizon ML tasks autonomously.
        </p>
        <div class="offline-commands">
          <div class="offline-command">
            <span class="offline-command-label">Install</span>
            <code class="offline-command-code">pip install luml-prisma</code>
          </div>
          <div class="offline-command">
            <span class="offline-command-label">Run</span>
            <code class="offline-command-code">luml-prisma</code>
          </div>
        </div>
      </template>

      <div class="url-input-group">
        <label class="url-label">Engine URL</label>
        <InputText
          v-model="backendUrl"
          placeholder="http://localhost:8420"
          class="url-input"
          @keydown.enter="onRetry"
        />
        <span class="url-hint">Default: http://localhost:8420</span>
      </div>

      <Button :loading="retrying" @click="onRetry">Retry</Button>
    </div>
  </div>
</template>

<style scoped>
.offline-container {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 2rem;
}

.offline-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  max-width: 360px;
  text-align: center;
}

.offline-icon {
  color: var(--p-text-muted-color);
  margin-bottom: 4px;
}

.offline-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.offline-hint {
  margin: 0;
  color: var(--p-text-muted-color);
  font-size: 0.9rem;
  line-height: 1.5;
}

.offline-commands {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  margin: 4px 0 4px;
}

.offline-command {
  display: grid;
  grid-template-columns: 56px 1fr;
  align-items: center;
  gap: 8px;
  text-align: left;
}

.offline-command-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
}

.offline-command-code {
  font-family: var(--p-font-family-mono, ui-monospace, monospace);
  font-size: 0.85rem;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--p-surface-100, rgba(127, 127, 127, 0.12));
  border: 1px solid var(--p-surface-200, rgba(127, 127, 127, 0.2));
  color: var(--p-text-color);
  overflow-x: auto;
  white-space: nowrap;
}

.url-input-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
}

.url-label {
  font-size: 0.8rem;
  font-weight: 500;
  text-align: left;
}

.url-input {
  width: 100%;
}

.url-hint {
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  text-align: left;
}
</style>
