<template>
  <div ref="wrapperRef">
    <Textarea
      v-bind="attrs"
      class="textarea"
      :class="{ scrollable: isScrollable }"
      :style="{ maxHeight: props.maxHeight + 'px' }"
    ></Textarea>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, useAttrs } from 'vue'
import { Textarea } from 'primevue'

type Props = {
  maxHeight: number
}

const props = defineProps<Props>()

const attrs = useAttrs()

const wrapperRef = ref()
const isScrollable = ref(false)
let observer: ResizeObserver | null = null

onMounted(() => {
  observer = new ResizeObserver((entries) => {
    for (const entry of entries) {
      isScrollable.value = entry.contentRect.height > props.maxHeight
    }
  })

  if (wrapperRef.value) {
    observer.observe(wrapperRef.value)
  }
})

onUnmounted(() => {
  if (observer) {
    observer.disconnect()
  }
})
</script>

<style scoped>
.textarea {
  resize: none;
}
.textarea.scrollable {
  overflow-y: auto !important;
}
</style>
