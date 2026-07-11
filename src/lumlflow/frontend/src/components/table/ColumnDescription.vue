<template>
  <div
    ref="container"
    v-tooltip.top="description"
    class="line-clamp-2 h-12 overflow-hidden text-ellipsis"
    :class="{ 'flex items-center': isFlex }"
    :style="style"
  >
    <span v-if="description">{{ description }}</span>
    <span v-else>-</span>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, ref, useTemplateRef, watch } from 'vue'

interface Props {
  description: string | null
  lines?: number
}

const props = withDefaults(defineProps<Props>(), {
  lines: 2,
})

const container = useTemplateRef<HTMLDivElement>('container')
const isFlex = ref(false)

const checkLines = async () => {
  await nextTick()
  if (!container.value) return

  isFlex.value = container.value.scrollHeight <= container.value.clientHeight
}

const style = computed(() => {
  return {
    '-webkit-line-clamp': props.lines,
    'line-clamp': props.lines,
  }
})

onMounted(checkLines)

watch(() => props.description, checkLines)
</script>

<style scoped></style>
