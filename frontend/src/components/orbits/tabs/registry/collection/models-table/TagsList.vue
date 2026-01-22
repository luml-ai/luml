<template>
  <div class="tags">
    <Tag v-for="(tag, index) in visibleTags" :key="index" class="tag">{{ tag }}</Tag>
    <span v-if="visibleTags.length < tags.length" class="more-tags">
      +{{ tags.length - visibleTags.length }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import { computed } from 'vue'

const CELL_WIDTH = 203
const MORE_TAGS_WIDTH = 30
const AVAILABLE_WIDTH = CELL_WIDTH - MORE_TAGS_WIDTH
const TAG_PADDING = 8
const GAP = 4
const LETTER_WIDTH = 10

type Props = {
  tags: string[]
}

const props = defineProps<Props>()

const visibleTags = computed(() => {
  const { tags } = props.tags.reduce(
    (acc, tag) => {
      const tagWidth = tag.length * LETTER_WIDTH + TAG_PADDING * 2
      if (acc.width + tagWidth > AVAILABLE_WIDTH) {
        return acc
      }
      acc.width += tagWidth + GAP
      acc.tags.push(tag)
      return acc
    },
    { tags: [] as string[], width: 0 },
  )
  return tags
})
</script>

<style scoped>
.tags {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 203px;
  overflow: hidden;
}

.tag {
  font-weight: 400;
}

.more-tags {
  color: var(--p-tag-primary-color);
  font-size: 12px;
}
</style>
