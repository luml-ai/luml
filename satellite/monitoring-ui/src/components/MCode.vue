<template>
  <div class="code">
    <pre class="code-content"><code>{{ code }}</code></pre>
    <MCopyButton class="code-copy" :text="code" :icon-size="14" />
  </div>
</template>

<script setup lang="ts">
import MCopyButton from '@/components/MCopyButton.vue'

interface Props {
  code: string
}

defineProps<Props>()
</script>

<style scoped>
.code {
  position: relative;
  display: flex;
  min-height: 0;
  border: 1px solid var(--p-listbox-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-listbox-option-focus-background);
}

.code-content {
  flex: 1;
  min-width: 0;
  margin: 0;
  padding: 8px 40px 8px 8px;
  overflow: auto;
  font-family: Consolas, 'SFMono-Regular', Menlo, monospace;
  font-size: 14px;
  color: var(--p-text-color);
  white-space: pre;
}

.code-copy {
  position: absolute;
  top: 8px;
  right: 8px;
}
</style>
