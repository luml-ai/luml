<template>
  <div class="placeholder-banner" data-testid="placeholder-banner" role="status">
    <Info :size="18" class="icon" />
    <div>
      <span class="title">Reference profile is a placeholder</span>
      <span class="detail">
        A real training baseline has not been loaded, so drift and distribution views are
        approximate until it is generated.
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
</script>

<style scoped>
.placeholder-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--luml-space-3);
  padding: var(--luml-space-4) var(--luml-space-5);
  border: 1px solid var(--luml-warn-tint-bg);
  border-radius: var(--luml-radius-lg);
  background: var(--luml-warn-tint-bg);
  color: var(--luml-warn-tint-fg);
}
.icon {
  flex-shrink: 0;
  margin-top: 1px;
}
.title {
  font-weight: 600;
  font-size: 13.5px;
}
.detail {
  margin-left: 8px;
  font-size: 13px;
  color: var(--luml-fg-muted);
}
</style>
