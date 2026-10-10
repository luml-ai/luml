<template>
  <Breadcrumb :model="crumbs" :pt="BREADCRUMBS_PT">
    <template #item="{ item, props }">
      <a v-if="item.path" href="#" v-bind="props.action" @click.prevent="open(item.path)">
        {{ item.label }}
      </a>
      <span v-else class="current">{{ item.label }}</span>
    </template>
  </Breadcrumb>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Breadcrumb, useToast } from 'primevue'
import type { MenuItem } from 'primevue/menuitem'
import { useWorkspaceStore } from '@/store/workspace'
import { errorToast } from '@/toasts'
import { BREADCRUMBS_PT } from '@/components/experiments/experiment/experiment.const'
import { pathSegments } from '@/helpers/path'

const workspaceStore = useWorkspaceStore()
const toast = useToast()

// Every ancestor is a link; the directory being listed is plain text.
const crumbs = computed<MenuItem[]>(() => {
  const segments = pathSegments(workspaceStore.currentDirectory ?? '')
  return segments.map(({ name, path }, index) => ({
    label: name,
    path: index < segments.length - 1 ? path : undefined,
  }))
})

async function open(path: string) {
  try {
    await workspaceStore.navigateToFolder(path)
  } catch (error) {
    toast.add(errorToast(error))
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.current {
  @apply text-(--p-breadcrumb-item-color);
}
</style>
