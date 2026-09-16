<template>
  <CellOutputTabContent :content="content" />
</template>

<script setup lang="ts">
import type { NotebookOutputProps } from '@/components/notebooks/cell/cell.interface'
import type { CellTabContent } from '@/composables/useCellTabs'
import { onBeforeMount, ref } from 'vue'
import { useFlowStore } from '@/store/flow'
import CellOutputTabContent from '@/components/notebooks/cell/preview/CellOutputTabContent.vue'

const props = defineProps<NotebookOutputProps>()

const flowStore = useFlowStore()

const content = ref<CellTabContent>({ status: 'loading' })

onBeforeMount(async () => {
  try {
    const asset = await flowStore.fetchAssetPreview(props.slug, props.name)
    content.value = asset.preview
      ? { status: 'ready', blocks: asset.preview.blocks, truncated: asset.preview.truncated }
      : { status: 'error', message: 'This output has not produced a value yet' }
  } catch (error) {
    content.value = {
      status: 'error',
      message: error instanceof Error ? error.message : 'Failed to load preview',
    }
  }
})
</script>

<style scoped></style>
