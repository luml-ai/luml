<template>
  <Card>
    <template #content>
      <div v-if="isLoading">
        <Skeleton v-for="i in 4" :key="i" height="40px" class="not-last:mb-1" />
      </div>
      <div v-else-if="items.length === 0">
        <p class="text-sm">No flows found in this directory</p>
      </div>
      <template v-else>
        <WorkspaceFolderItem v-for="item in items" :key="item.id" :item="item" />
      </template>
    </template>
  </Card>
</template>

<script setup lang="ts">
import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { Card, Skeleton } from 'primevue'
import { useWorkspaceStore } from '@/store/workspace'
import { computed } from 'vue'
import WorkspaceFolderItem from './WorkspaceFolderItem.vue'

const workspaceStore = useWorkspaceStore()

const isLoading = computed(() => workspaceStore.isDirectoryLoading)

interface Props {
  items: IWorkspaceFolderItem[]
}

defineProps<Props>()
</script>

<style scoped></style>
