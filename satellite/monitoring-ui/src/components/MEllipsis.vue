<template>
  <span ref="element" v-tooltip.top="isTruncated ? text : undefined" class="ellipsis">
    {{ text }}
  </span>
</template>

<script setup lang="ts">
import { ref, useTemplateRef, watch } from 'vue'
import { useResizeObserver } from '@vueuse/core'

interface Props {
  text: string
}

const props = defineProps<Props>()

const element = useTemplateRef<HTMLSpanElement>('element')
const isTruncated = ref(false)

function measure() {
  if (!element.value) return
  isTruncated.value = element.value.scrollWidth > element.value.clientWidth
}

useResizeObserver(element, measure)

watch(() => props.text, measure, { flush: 'post' })
</script>

<style scoped>
.ellipsis {
  display: block;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>
