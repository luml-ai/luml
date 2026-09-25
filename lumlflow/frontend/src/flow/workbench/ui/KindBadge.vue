<template>
  <span class="inline-flex items-center gap-1.5 text-muted-color">
    <component :is="icon" :size="iconSize" class="shrink-0" />
    <span v-if="!iconOnly" class="text-sm">{{ label }}</span>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { KIND_LABELS } from '../model/registry'
import type { AssetKind } from '../model/types'
import { KIND_ICONS } from './kinds'

const props = defineProps<{
  kind: AssetKind
  iconOnly?: boolean
  iconSize?: number
}>()

const icon = computed(() => KIND_ICONS[props.kind] ?? KIND_ICONS.unknown)
const label = computed(() => KIND_LABELS[props.kind] ?? props.kind)
const iconSize = computed(() => props.iconSize ?? 14)
</script>
