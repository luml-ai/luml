<template>
  <div class="session-overlay" data-testid="session-expired">
    <div class="session-card card">
      <Clock :size="34" class="icon" />
      <h1 class="title">Session expired</h1>
      <p class="detail">
        Your monitoring session has ended. Reopen monitoring from the Platform to continue.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Clock } from 'lucide-vue-next'
</script>

<style scoped>
.session-overlay {
  position: fixed;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--luml-space-6);
  background: var(--luml-bg);
}
.session-card {
  max-width: 420px;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--luml-space-3);
}
.icon {
  color: var(--luml-fg-faint);
}
.title {
  margin: 0;
  font-size: var(--luml-text-xl);
  font-weight: 500;
  color: var(--luml-fg-strong);
}
.detail {
  margin: 0;
  color: var(--luml-fg-muted);
}
</style>
