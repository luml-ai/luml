<template>
  <div class="card" :data-testid="`flow-card-${kind}`">
    <div class="header">
      <h3 class="title">
        <div class="status" v-tooltip.top="statusTooltip" :class="statusClass"></div>
        <span class="name">{{ name }}</span>
      </h3>
      <div class="actions">
        <slot name="actions" />
      </div>
    </div>
    <div class="body">
      <slot />
    </div>
    <div class="kind" data-testid="flow-kind">
      <template v-if="kind === 'local'">
        <Laptop :size="12" />
        <span>Local</span>
      </template>
      <template v-else>
        <Globe :size="12" />
        <span>Relayed</span>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Globe, Laptop } from 'lucide-vue-next'

type Props = {
  name: string
  kind: 'local' | 'relayed'
  statusClass: string
  statusTooltip: string
}

defineProps<Props>()
</script>

<style scoped>
.card {
  padding: 16px 16px 20px;
  border-radius: 8px;
  background-color: var(--p-card-background);
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--p-card-shadow);
  min-height: 149px;
  display: flex;
  flex-direction: column;
}

.header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}

.title {
  font-size: 16px;
  font-weight: 500;
  display: flex;
  gap: 6px;
  align-items: center;
  min-width: 0;
}

.name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.actions {
  display: flex;
  flex-shrink: 0;
}

.status {
  width: 20px;
  height: 20px;
  flex: 0 0 auto;
  border-radius: 50%;
  border: 1px solid var(--p-content-border-color);
  display: flex;
  justify-content: center;
  align-items: center;
}

.status::before {
  content: '';
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: var(--p-content-border-color);
}

.status--success {
  border-color: var(--p-toast-success-border-color);
  background-color: var(--p-toast-success-background);
}

.status--success::before {
  background-color: var(--p-badge-success-background);
  box-shadow: 0 2px 8px 0 rgba(34, 197, 94, 0.5);
}

.status--warn {
  border-color: var(--p-toast-warn-border-color);
  background-color: var(--p-toast-warn-background);
}

.status--warn::before {
  background-color: var(--p-badge-warn-background);
  box-shadow: 0 2px 8px 0 rgba(249, 115, 22, 0.5);
}

.status--danger {
  border-color: var(--p-toast-error-border-color);
  background-color: var(--p-toast-error-background);
}

.status--danger::before {
  background-color: var(--p-badge-danger-background);
  box-shadow: 0 2px 8px 0 rgba(249, 115, 22, 0.5);
}

.body {
  padding: 0 8px 0 4px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1 1 auto;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.kind {
  align-self: flex-end;
  display: flex;
  align-items: center;
  gap: 4px;
  padding-top: 12px;
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  color: var(--p-text-muted-color);
}
</style>
