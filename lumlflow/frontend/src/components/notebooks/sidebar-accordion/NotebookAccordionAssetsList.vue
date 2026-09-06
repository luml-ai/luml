<template>
  <div>
    <NotebookAccordionAssetsListItem
      v-for="item in list"
      :key="item.id"
      :item="item"
      :show-icon="showIcons"
      class="not-last:mb-2"
    />
  </div>
</template>

<script setup lang="ts">
import type { NotebookAssetInterface } from '@/components/notebooks/notebooks.interface'
import NotebookAccordionAssetsListItem from '@/components/notebooks/sidebar-accordion/NotebookAccordionAssetsListItem.vue'

interface Props {
  list: NotebookAssetInterface[]
  showIcons?: boolean
}

defineProps<Props>()
</script>

<style scoped></style>
