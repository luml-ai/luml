<template>
  <header class="header">
    <div class="label">
      Trace <span class="count">({{ count }} {{ count === 1 ? 'item' : 'items' }})</span>
    </div>
    <Button
      v-tooltip.top="expanded ? 'Collapse all' : 'Expand all'"
      severity="secondary"
      variant="outlined"
      :aria-label="expanded ? 'Collapse all spans' : 'Expand all spans'"
      @click="$emit('toggle')"
    >
      <template #icon>
        <component :is="expanded ? FoldVertical : UnfoldVertical" :size="14" />
      </template>
    </Button>
  </header>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { FoldVertical, UnfoldVertical } from 'lucide-vue-next'

interface Props {
  count: number
  expanded: boolean
}

type Emits = {
  toggle: []
}

defineProps<Props>()

defineEmits<Emits>()
</script>

<style scoped>
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
}

.label {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.count {
  font-weight: 400;
  font-variant-numeric: lining-nums tabular-nums;
  color: var(--p-text-muted-color);
}
</style>
