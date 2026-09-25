<template>
  <span class="inline-flex items-center gap-1.5 min-w-0 text-base">
    <span class="w-2.5 h-2.5 rounded-full shrink-0" :style="{ background: color }" />
    <span class="font-mono text-base truncate">{{ name }}</span>
    <Tag v-if="checkedOut" value="on disk" severity="secondary" :pt="tinyTag" />
    <Tag v-if="archived" value="archived" severity="secondary" :pt="tinyTag" class="opacity-60" />
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Tag } from 'primevue'
import { branchColor } from './kinds'

const props = defineProps<{
  name: string
  checkedOut?: boolean
  archived?: boolean
}>()

const color = computed(() => branchColor(props.name))
const tinyTag = { root: { class: 'text-sm font-normal px-1.5 py-0' } }
</script>
