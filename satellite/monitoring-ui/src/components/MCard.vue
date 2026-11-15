<template>
  <Card class="card" :class="severityClass">
    <template #title>
      <h3 class="label">{{ label }}</h3>
    </template>
    <template #content>
      <slot name="default">
        <span class="content">{{ content }}</span>
      </slot>
    </template>
    <template #footer>
      <div v-if="$slots.footer" class="footer">
        <slot name="footer" />
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { computed, type VNode } from 'vue'
import Card from 'primevue/card'
import { CardSeverity } from '@/types/card'

interface Props {
  label: string
  severity?: CardSeverity
  content?: string
}

interface Slots {
  default: () => VNode
  footer: () => VNode
}

const props = withDefaults(defineProps<Props>(), {
  severity: CardSeverity.DEFAULT,
})

defineSlots<Slots>()

const severityClass = computed(() => `card--${props.severity}`)
</script>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  border: 1px solid var(--p-content-border-color);
}

.label {
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.content {
  font-weight: 500;
  font-size: 24px;
}

.footer {
  font-size: 12px;
}

.card--danger {
  border-color: var(--p-message-error-border-color);
  color: var(--p-message-error-color);
}

.card--danger .label {
  color: var(--p-message-error-color);
}

.card--warning {
  border-color: var(--p-message-warn-border-color);
  color: var(--p-message-warn-color);
}

.card--warning .label {
  color: var(--p-message-warn-color);
}

.card--warning .footer {
  color: var(--p-message-warn-color);
}
</style>
