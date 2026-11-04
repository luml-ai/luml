<template>
  <span
    v-tooltip.bottom="'This feature is in preview and may change as we refine it.'"
    class="preview-badge"
  >
    PREVIEW
  </span>
</template>

<style scoped>
.preview-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 6px;
  border-radius: 6px;
  color: var(--p-primary-color);
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.05em;
  cursor: help;
}
</style>
