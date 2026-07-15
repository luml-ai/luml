<template>
  <span class="severity-tag" :class="`sev-${severity}`" data-testid="severity-tag">
    {{ label }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Severity } from '@/api/types'
import { severityLabel } from '@/lib/format'

const props = defineProps<{ severity: Severity }>()

const label = computed(() => severityLabel(props.severity))
</script>

<style scoped>
.severity-tag {
  display: inline-block;
  padding: 2px 9px;
  border-radius: var(--luml-radius-pill);
  font-size: 12px;
  font-weight: 500;
  line-height: 1.4;
}
.sev-ok {
  background: var(--luml-success-tint-bg);
  color: var(--luml-success-tint-fg);
}
.sev-warning {
  background: var(--luml-warn-tint-bg);
  color: var(--luml-warn-tint-fg);
}
.sev-critical {
  background: var(--luml-danger-tint-bg);
  color: var(--luml-danger-tint-fg);
}
</style>
