<template>
  <Card>
    <template #content>
      <WorkspaceFolderItem v-for="item in items" :key="item.id" :item="item" />
    </template>
  </Card>
</template>

<script setup lang="ts">
import type { IWorkspaceFolderItem } from '@/components/workspace/folder/interface'
import { Card } from 'primevue'
import WorkspaceFolderItem from './WorkspaceFolderItem.vue'

interface Props {
  items: IWorkspaceFolderItem[]
}

defineProps<Props>()
</script>

<style scoped></style>
