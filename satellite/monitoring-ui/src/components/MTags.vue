<template>
  <div ref="container" class="tags">
    <Tag v-for="tag in visibleTags" :key="tag" :value="tag" severity="secondary" />
    <button
      v-if="hiddenTags.length"
      type="button"
      class="more"
      :aria-expanded="isPopoverOpen"
      @click="popover?.toggle($event)"
    >
      +{{ hiddenTags.length }}
    </button>
    <div ref="measure" class="tags tags-measure" aria-hidden="true">
      <Tag v-for="tag in tags" :key="tag" :value="tag" severity="secondary" />
      <span class="more">+{{ tags.length }}</span>
    </div>
    <Popover ref="popover" @show="isPopoverOpen = true" @hide="isPopoverOpen = false">
      <div class="popover-list">
        <Tag v-for="tag in hiddenTags" :key="tag" :value="tag" severity="secondary" />
      </div>
    </Popover>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, useTemplateRef, watch } from 'vue'
import { useElementSize, useResizeObserver } from '@vueuse/core'
import Tag from 'primevue/tag'
import Popover from 'primevue/popover'

const GAP = 5

interface Props {
  tags: string[]
}

const props = withDefaults(defineProps<Props>(), {
  tags: () => [],
})

const container = useTemplateRef<HTMLDivElement>('container')
const measure = useTemplateRef<HTMLDivElement>('measure')
const popover = useTemplateRef<InstanceType<typeof Popover>>('popover')

const isPopoverOpen = ref(false)
const tagWidths = ref<number[]>([])
const moreWidth = ref(0)

const { width: containerWidth } = useElementSize(container)

function measureTags() {
  const children = Array.from(measure.value?.children ?? []) as HTMLElement[]
  const more = children.pop()
  tagWidths.value = children.map((child) => child.offsetWidth)
  moreWidth.value = more?.offsetWidth ?? 0
}

useResizeObserver(measure, measureTags)

watch(() => props.tags, measureTags, { deep: true, flush: 'post' })

const visibleCount = computed(() => {
  const widths = tagWidths.value
  if (widths.length !== props.tags.length) return 0
  let used = 0
  for (const [index, width] of widths.entries()) {
    const next = used + (index > 0 ? GAP : 0) + width
    const reserve = index < widths.length - 1 ? GAP + moreWidth.value : 0
    if (next + reserve > containerWidth.value) return index
    used = next
  }
  return widths.length
})

const visibleTags = computed(() => props.tags.slice(0, visibleCount.value))

const hiddenTags = computed(() => props.tags.slice(visibleCount.value))

const gapPx = `${GAP}px`
</script>

<style scoped>
.tags {
  position: relative;
  display: flex;
  align-items: center;
  gap: v-bind(gapPx);
  min-width: 0;
  overflow: hidden;
}

.tags-measure {
  position: absolute;
  top: 0;
  left: 0;
  visibility: hidden;
  pointer-events: none;
  white-space: nowrap;
}

.tags-measure > * {
  flex-shrink: 0;
}

.more {
  flex-shrink: 0;
  padding: 0;
  border: none;
  background: none;
  font-size: 14px;
  color: var(--p-primary-color);
  cursor: pointer;
}

.popover-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 260px;
}
</style>
