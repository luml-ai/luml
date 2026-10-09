<template>
  <!-- Teleported so it covers the trace dialog too, not just the panel it was opened from. -->
  <Teleport to="body">
    <div
      class="viewer"
      role="dialog"
      aria-modal="true"
      :aria-label="name"
      data-testid="field-fullscreen"
    >
      <header class="head">
        <div class="identity">
          <p class="eyebrow">{{ eyebrow }}</p>
          <h3 class="name mono">{{ name }}</h3>
          <p class="size">{{ sizeLabel }}</p>
        </div>
        <div class="actions">
          <CopyButton :value="value" :label="name" />
          <button
            type="button"
            class="close"
            aria-label="Close full screen"
            data-testid="field-fullscreen-close"
            @click="$emit('close')"
          >
            <X :size="16" />
          </button>
        </div>
      </header>
      <pre class="mono body">{{ value }}</pre>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { X } from 'lucide-vue-next'
import CopyButton from '@/components/CopyButton.vue'

const props = withDefaults(defineProps<{ name: string; value: string; eyebrow?: string }>(), {
  eyebrow: 'Span field',
})

const emit = defineEmits<{ close: [] }>()

const sizeLabel = computed(() => {
  const lines = props.value.split('\n').length
  return `${lines} line${lines === 1 ? '' : 's'} · ${props.value.length} characters`
})

function onKeydown(event: KeyboardEvent): void {
  // Escape belongs to the topmost layer: swallow it so the trace dialog stays open.
  if (event.key !== 'Escape') return
  event.stopPropagation()
  emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown, true)
  document.body.style.overflow = 'hidden'
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown, true)
  document.body.style.overflow = ''
})
</script>

<style scoped>
.viewer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  background: var(--luml-bg);
}
.head {
  flex: 0 0 auto;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--luml-space-4);
  padding: 14px 20px;
  border-bottom: 1px solid var(--luml-border);
  background: var(--luml-bg-card);
}
.eyebrow {
  margin: 0 0 4px;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--luml-fg-muted);
}
.name {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--luml-fg-strong);
  word-break: break-all;
}
.size {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--luml-fg-muted);
  font-variant-numeric: tabular-nums;
}
.actions {
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--luml-space-2);
}
.close {
  display: inline-flex;
  padding: 5px;
  border: 1px solid var(--luml-border);
  border-radius: var(--luml-radius-md);
  background: var(--luml-bg-card);
  color: var(--luml-fg-muted);
  cursor: pointer;
}
.close:hover {
  background: var(--luml-bg-hover);
}
.body {
  flex: 1 1 auto;
  margin: 0;
  overflow: auto;
  padding: 18px 20px;
  font-size: 12.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
  color: var(--luml-fg);
}
</style>
