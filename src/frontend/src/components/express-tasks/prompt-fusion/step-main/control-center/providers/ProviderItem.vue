<template>
  <div class="item" :class="{ disabled: provider.disabled }">
    <div class="left">
      <img class="image" :src="provider.image" :alt="provider.name" />
      <h3 class="title">{{ provider.name }}</h3>
      <span v-if="provider.disabled" class="disabled-label">(Not Available)</span>
    </div>
    <div v-if="!provider.disabled" class="right">
      <div class="status" :class="{ connected: provider.status === ProviderStatus.connected }">
        {{ provider.status }}
      </div>
      <d-button
        severity="secondary"
        variant="text"
        rounded
        @click.stop="promptFusionService.openProviderSettings(provider.id)"
      >
        <template #icon>
          <bolt :size="14" color="var(--p-button-text-secondary-color)" />
        </template>
      </d-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ProviderStatus, type BaseProviderInfo } from '@/lib/promt-fusion/prompt-fusion.interfaces'
import { Bolt } from 'lucide-vue-next'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'

type Props = {
  provider: BaseProviderInfo
}

defineProps<Props>()
</script>

<style scoped>
.item {
  padding: 16px 12px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 15px;
  border-radius: 8px;
  border: 1px solid transparent;
  background-color: var(--p-content-background);
  transition: border-color 0.2s;
}
.item.selected {
  border-color: var(--p-primary-color);
}
.item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.left {
  display: flex;
  align-items: center;
  gap: 15px;
}
.image {
  width: 25px;
  display: flex;
  justify-content: center;
  align-items: center;
}
.title {
  font-size: 18px;
  font-weight: 600;
}
.right {
  display: flex;
  align-items: center;
  gap: 8px;
}
.status {
  border-radius: 16px;
  border: 1px solid var(--p-toast-error-border-color);
  background-color: var(--p-toast-error-background);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 8px 4px 6px;
  font-size: 12px;
  font-weight: 500;
  line-height: 1.5;
  text-transform: capitalize;
}
.status::before {
  content: '';
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: 0 0 auto;
  background-color: var(--p-badge-danger-background);
  box-shadow: 0px 2px 8px 0px rgba(239, 68, 68, 0.5);
}
.status.connected {
  border-color: var(--p-toast-success-border-color);
  background-color: var(--p-toast-success-background);
}
.status.connected::before {
  background-color: var(--p-badge-success-background);
  box-shadow: 0px 2px 8px 0px rgba(34, 197, 94, 0.5);
}
.disabled-label {
  font-size: 12px;
  font-style: italic;
  color: var(--p-text-muted-color);
  margin-left: 8px;
}
</style>
