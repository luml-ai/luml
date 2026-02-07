<template>
  <div class="flex items-center gap-1 flex-nowrap overflow-hidden">
    <Tag v-for="(tag, index) in visibleTags" :key="index" class="font-normal">{{ tag }}</Tag>
    <span v-if="visibleTags.length < tags.length" class="text-xs text-(--p-tag-primary-color)">
      +{{ tags.length - visibleTags.length }}
    </span>
  </div>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import { computed } from 'vue'

const MORE_TAGS_WIDTH = 30
const TAG_PADDING = 8
const GAP = 4
const LETTER_WIDTH = 10

interface Props {
  width?: number
  tags: string[]
}

const props = withDefaults(defineProps<Props>(), {
  width: 203,
})

const availableWidth = computed(() => {
  return props.width - MORE_TAGS_WIDTH
})

const visibleTags = computed(() => {
  const { tags } = props.tags.reduce(
    (acc, tag) => {
      const tagWidth = tag.length * LETTER_WIDTH + TAG_PADDING * 2
      if (acc.width + tagWidth > availableWidth.value) {
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

<style scoped></style>
