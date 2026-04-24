<script setup lang="ts">
import { ChartSpline } from 'lucide-vue-next'
</script>

<template>
  <div class="flow-page">
    <div class="flow-container">
      <div class="flow-card">
        <ChartSpline :size="48" class="flow-icon" />

        <h3 class="flow-title">Run Flow locally</h3>
        <div class="flow-hint">
          <p>Flow is a local live tracker for ML experiments.</p>
          <p>Log parameters, metrics, and artifacts as they stream in.</p>
          <p>Compare them side by side in a browser UI.</p>
        </div>

        <div class="flow-commands">
          <div class="flow-command">
            <span class="flow-command-label">Install</span>
            <code class="flow-command-code">pip install lumlflow</code>
          </div>
          <div class="flow-command">
            <span class="flow-command-label">Run</span>
            <code class="flow-command-code">lumlflow ui</code>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.flow-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 130px);
  padding-top: 32px;
}

.flow-container {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  padding: 2rem;
}

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
  background: var(--p-surface-100, rgba(127, 127, 127, 0.12));
  border: 1px solid var(--p-surface-200, rgba(127, 127, 127, 0.2));
  color: var(--p-text-color);
  overflow-x: auto;
  white-space: nowrap;
}
</style>
