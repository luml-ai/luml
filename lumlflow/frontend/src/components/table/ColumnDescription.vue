<template>
  <div
    v-tooltip.top="description"
    class="line-clamp-2 h-10.5 flex flex-col justify-center"
    :style="style"
  >
    {{ description }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  description: string
  lines?: number
}

const props = withDefaults(defineProps<Props>(), {
  lines: 2,
})

const style = computed(() => {
  return {
    '-webkit-line-clamp': props.lines,
    'line-clamp': props.lines,
  }
})
</script>

<style scoped></style>
