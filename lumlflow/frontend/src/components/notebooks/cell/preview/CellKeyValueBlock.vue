<template>
  <div class="kv" :class="{ 'kv--clamped': hiddenRows > 0 }">
    <dl class="kv-list">
      <template v-for="[name, value] in visible" :key="name">
        <dt class="kv-name">{{ name }}</dt>
        <dd class="kv-value">{{ value ?? '–' }}</dd>
      </template>
    </dl>
  </div>
</template>

<script setup lang="ts">
import type { CellKeyValueBlockProps } from './preview.interface'
import { computed } from 'vue'

const props = defineProps<CellKeyValueBlockProps>()

const visible = computed(() => (props.limit ? props.entries.slice(0, props.limit) : props.entries))
const hiddenRows = computed(() => props.entries.length - visible.value.length)
</script>

<style scoped>
@reference "@/assets/css/index.css";

.kv {
  @apply relative;
}
/* The last rows fade out: the list goes on, in the expanded cell. */
.kv--clamped {
  mask-image: linear-gradient(to bottom, black 70%, transparent);
}
.kv-list {
  @apply grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm;
}
.kv-name {
  @apply text-muted-color;
}
.kv-value {
  @apply font-medium wrap-break-word;
}
</style>
