<template>
  <div class="span-title" :class="size">
    <div class="name">
      <component
        :is="spanType.icon"
        :size="size === 'large' ? 14 : 12"
        :color="spanType.color"
        :stroke-width="3"
        class="icon"
      />
      <MEllipsis class="text" :text="span.name" />
    </div>
    <div class="info">
      <History :size="12" />
      <span>{{ duration }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { History } from 'lucide-vue-next'
import type { TraceSpan } from '@/api/monitoring/interfaces'
import { formatSpanDuration, getSpanTypeData } from '@/utils/traces'
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  span: TraceSpan
  size?: 'default' | 'large'
}

const props = withDefaults(defineProps<Props>(), { size: 'default' })

const spanType = computed(() => getSpanTypeData(props.span.dfs_span_type))

const duration = computed(() => formatSpanDuration(props.span))
</script>

<style scoped>
.span-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.name {
  display: flex;
  align-items: center;
  gap: 4px;
  min-width: 0;
}

.large .name {
  gap: 8px;
}

.text {
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.large .text {
  font-size: 16px;
}

.icon {
  flex-shrink: 0;
}

.info {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 0 8px;
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
