<script setup lang="ts">
import { ref } from 'vue'
import { Button, InputText, Popover } from 'primevue'
import { api } from '@/lib/api'

const emit = defineEmits<{ changed: [] }>()

const popover = ref()
const url = ref(api.dataAgent.getBackendUrl())

function displayHost(): string {
  try {
    return new URL(url.value).host
  } catch {
    return url.value
  }
}

function toggle(event: Event) {
  url.value = api.dataAgent.getBackendUrl()
  popover.value.toggle(event)
}

function save() {
  api.dataAgent.setBackendUrl(url.value)
  popover.value.hide()
  emit('changed')
}
</script>

<template>
  <button class="indicator" @click="toggle">
    <span class="dot" />
    <span class="host">{{ displayHost() }}</span>
  </button>

  <Popover ref="popover">
    <div class="popover-content">
      <label class="popover-label">Backend URL</label>
      <InputText
        v-model="url"
        placeholder="http://localhost:8420"
        class="popover-input"
        @keydown.enter="save"
      />
      <Button size="small" @click="save">Save</Button>
    </div>
  </Popover>
</template>

<style scoped>
.indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: none;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  padding: 4px 10px;
  cursor: pointer;
  font-size: 0.75rem;
  color: var(--p-text-muted-color);
  transition: border-color 0.15s;
}

.indicator:hover {
  border-color: var(--p-primary-color);
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--p-green-500);
  flex-shrink: 0;
}

.host {
  white-space: nowrap;
}

.popover-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-width: 260px;
}

.popover-label {
  font-size: 0.8rem;
  font-weight: 500;
}

.popover-input {
  width: 100%;
}
</style>
