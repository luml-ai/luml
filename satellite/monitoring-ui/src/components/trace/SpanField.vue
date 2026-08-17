<template>
  <div class="entry" data-testid="span-field">
    <div class="row">
      <p class="key" :title="name">{{ name }}</p>
      <div class="actions">
        <span v-if="lines > 1" class="size">{{ sizeLabel }}</span>
        <button
          type="button"
          class="expand"
          :aria-label="`Open ${name} full screen`"
          title="Open full screen"
          data-testid="span-field-expand"
          @click="$emit('expand')"
        >
          <Maximize2 :size="13" />
        </button>
        <CopyButton :value="value" :label="name" />
      </div>
    </div>
    <pre class="mono value">{{ value }}</pre>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Maximize2 } from 'lucide-vue-next'
import CopyButton from '@/components/CopyButton.vue'

const props = defineProps<{ name: string; value: string }>()
defineEmits<{ expand: [] }>()

const lines = computed(() => props.value.split('\n').length)

// Payloads are the reason the full-screen view exists; say how much is hidden below the fold.
const sizeLabel = computed(() => `${lines.value} lines · ${props.value.length} chars`)
</script>

<style scoped>
.row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--luml-space-3);
  margin-bottom: 4px;
}
.key {
  margin: 0;
  font-size: 11px;
  color: var(--luml-fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: 4px;
}
.size {
  font-size: 10.5px;
  color: var(--luml-fg-muted);
  font-variant-numeric: tabular-nums;
}
.expand {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 3px;
  border: 1px solid transparent;
  border-radius: var(--luml-radius-sm, 4px);
  background: transparent;
  color: var(--luml-fg-muted);
  cursor: pointer;
  line-height: 0;
}
.expand:hover {
  border-color: var(--luml-border);
  background: var(--luml-bg-card);
  color: var(--luml-fg-strong);
}
.value {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  padding: 8px 10px;
  border: 1px solid var(--luml-surface-100);
  border-radius: var(--luml-radius-md);
  background: var(--luml-surface-100);
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
