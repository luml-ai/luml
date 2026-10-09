<template>
  <div ref="containerRef" class="tags">
    <Tag v-for="tag in visibleTags" :key="tag" class="tag">
      <TagIcon :size="12" class="tag-icon" />
      <span>{{ tag }}</span>
    </Tag>
    <span v-if="hiddenCount > 0" class="tag-more">+{{ hiddenCount }}</span>
  </div>
  <div class="tags-measure" aria-hidden="true">
    <Tag v-for="tag in tags" :key="tag" ref="measureTagRefs" class="tag">
      <TagIcon :size="12" class="tag-icon" />
      <span>{{ tag }}</span>
    </Tag>
    <span ref="measureMoreRef" class="tag-more">+{{ tags.length }}</span>
  </div>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import { Tag as TagIcon } from 'lucide-vue-next'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue'

type Props = {
  tags: string[]
}

const props = defineProps<Props>()

const containerRef = useTemplateRef<HTMLElement>('containerRef')
const measureTagRefs = useTemplateRef<{ $el: HTMLElement }[]>('measureTagRefs')
const measureMoreRef = useTemplateRef<HTMLElement>('measureMoreRef')

const visibleCount = ref(props.tags.length)

const visibleTags = computed(() => props.tags.slice(0, visibleCount.value))
const hiddenCount = computed(() => props.tags.length - visibleCount.value)

let resizeObserver: ResizeObserver | null = null

function recalcVisibleTags() {
  const tags = props.tags
  const container = containerRef.value

  if (!container || tags.length === 0) {
    visibleCount.value = tags.length
    return
  }

  const tagElements = (measureTagRefs.value ?? []).map((instance) => instance.$el)
  const moreElement = measureMoreRef.value

  if (tagElements.length !== tags.length || !moreElement) {
    return
  }

  const containerWidth = container.clientWidth
  const gap = parseFloat(getComputedStyle(container).columnGap || '0') || 0

  let usedWidth = 0
  let fitCount = 0

  for (let i = 0; i < tagElements.length; i++) {
    const tagWidth = tagElements[i].offsetWidth
    const candidateWidth = usedWidth + (i > 0 ? gap : 0) + tagWidth
    const remainingCount = tags.length - (i + 1)
    const moreWidth = remainingCount > 0 ? gap + moreElement.offsetWidth : 0

    if (candidateWidth + moreWidth > containerWidth) {
      break
    }

    usedWidth = candidateWidth
    fitCount = i + 1
  }

  visibleCount.value = fitCount
}

onMounted(() => {
  nextTick(() => recalcVisibleTags())
  resizeObserver = new ResizeObserver(() => recalcVisibleTags())
  if (containerRef.value) {
    resizeObserver.observe(containerRef.value)
  }
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
})

watch(
  () => props.tags,
  () => nextTick(() => recalcVisibleTags()),
  { deep: true },
)
</script>

<style scoped>
.tags {
  overflow: hidden;
  display: flex;
  align-items: center;
  gap: 12px;
}
.tags-measure {
  position: fixed;
  top: -9999px;
  left: -9999px;
  display: flex;
  align-items: center;
  gap: 12px;
  visibility: hidden;
  pointer-events: none;
}
.tag {
  font-size: 12px;
  font-weight: 400;
  white-space: nowrap;
  flex-shrink: 0;
}
.tag-icon {
  transform: scaleX(-1);
}
.tag-more {
  font-size: 14px;
  color: var(--p-text-link-color);
  white-space: nowrap;
  flex-shrink: 0;
}
</style>
