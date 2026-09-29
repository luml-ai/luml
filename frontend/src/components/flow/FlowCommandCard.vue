<script setup lang="ts">
import { ChartSpline } from 'lucide-vue-next'

export interface FlowCommand {
  label: string
  code: string
}

defineProps<{
  title: string
  hints: string[]
  commands: FlowCommand[]
}>()
</script>

<template>
  <div class="flow-card">
    <ChartSpline :size="48" class="flow-icon" />

    <h3 class="flow-title">{{ title }}</h3>
    <div class="flow-hint">
      <p v-for="hint in hints" :key="hint">{{ hint }}</p>
    </div>

    <div class="flow-commands">
      <div v-for="command in commands" :key="command.label" class="flow-command">
        <span class="flow-command-label">{{ command.label }}</span>
        <code class="flow-command-code">{{ command.code }}</code>
      </div>
    </div>
  </div>
</template>

<style scoped>
.flow-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
  max-width: 480px;
  text-align: center;
}

.flow-icon {
  color: var(--p-text-muted-color);
  margin-bottom: 4px;
}

.flow-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
}

.flow-hint {
  display: flex;
  flex-direction: column;
  gap: 2px;
  color: var(--p-text-muted-color);
  font-size: 0.9rem;
  line-height: 1.5;
}

.flow-hint p {
  margin: 0;
}

.flow-commands {
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  margin: 4px 0;
}

.flow-command {
  display: grid;
  grid-template-columns: 56px 1fr;
  align-items: center;
  gap: 8px;
  text-align: left;
}

.flow-command-label {
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--p-text-muted-color);
}

.flow-command-code {
  font-family: var(--p-font-family-mono, ui-monospace, monospace);
  font-size: 0.85rem;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--p-content-hover-background);
  border: 1px solid var(--p-divider-border-color);
  color: var(--p-text-color);
  overflow-x: auto;
  white-space: nowrap;
}
</style>
