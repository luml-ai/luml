<template>
  <CellOutputTabContent :content="content" />
</template>

<script setup lang="ts">
import type { NotebookOutputProps } from '@/components/notebooks/cell/cell.interface'
import type { CellTabContent } from '@/composables/useCellTabs'
import { ref, watch } from 'vue'
import { useFlowStore } from '@/store/flow'
import { useCellPanelPayload } from '@/composables/useCellPanelPayload'
import CellOutputTabContent from '@/components/notebooks/cell/preview/CellOutputTabContent.vue'

const props = defineProps<NotebookOutputProps>()

const flowStore = useFlowStore()

const content = ref<CellTabContent>({ status: 'loading' })

const { reload } = useCellPanelPayload({
  slug: () => props.slug,
  follows: (cell) => cell.mat_id,
  fetch: () => flowStore.fetchAssetPreview(props.slug, props.name),
  onLoaded: (asset) => {
    content.value = asset.preview
      ? { status: 'ready', blocks: asset.preview.blocks, truncated: asset.preview.truncated }
      : { status: 'error', message: 'This output has not produced a value yet' }
  },
  onFailed: (error) => {
    content.value = {
      status: 'error',
      message: error instanceof Error ? error.message : 'Failed to load preview',
    }
  },
})

watch(() => flowStore.experimentRemovals[props.slug], reload)
</script>

<style scoped></style>
