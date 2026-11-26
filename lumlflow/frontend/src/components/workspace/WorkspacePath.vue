<template>
  <Breadcrumb :model="crumbs" :pt="BREADCRUMBS_PT">
    <template #item="{ item, props }">
      <a
        v-if="item.path"
        href="#"
        v-bind="props.action"
        @click.prevent="emit('navigate', item.path)"
      >
        {{ item.label }}
      </a>
      <span v-else class="current">{{ item.label }}</span>
    </template>
  </Breadcrumb>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Breadcrumb } from 'primevue'
import type { MenuItem } from 'primevue/menuitem'
import { useWorkspaceStore } from '@/store/workspace'
import { BREADCRUMBS_PT } from '@/components/experiments/experiment/experiment.const'
import { pathSegments } from '@/helpers/path'

const props = defineProps<{ path?: string }>()
const workspaceStore = useWorkspaceStore()
const emit = defineEmits<{ navigate: [path: string] }>()

// Every ancestor is a link; the location shown (by default the listed directory) is plain text.
const crumbs = computed<MenuItem[]>(() => {
  const location = props.path ?? workspaceStore.currentDirectory ?? ''
  const segments = pathSegments(location)
  if (location.startsWith('/')) segments.unshift({ name: '/', path: '/' })
  return segments.map(({ name, path }, index) => ({
    label: name,
    path: index < segments.length - 1 ? path : undefined,
  }))
})
</script>

<style scoped>
@reference "@/assets/css/index.css";

.current {
  @apply text-(--p-breadcrumb-item-color);
}
/* Long paths wrap whole segments, so the current directory stays visible beside the page actions. */
.p-breadcrumb :deep(.p-breadcrumb-list) {
  flex-wrap: wrap;
}
.p-breadcrumb :deep(.p-breadcrumb-item) {
  white-space: nowrap;
}
</style>
