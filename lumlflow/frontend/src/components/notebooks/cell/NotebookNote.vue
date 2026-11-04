<template>
  <p v-if="isLoading" class="text-sm text-muted-color">Loading note…</p>
  <CellMarkdownBlock v-else-if="doc" :block="{ block: 'markdown', text: doc }" class="note" />
  <p v-else class="text-sm text-muted-color">This note is empty</p>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { useCellPanelPayload } from '@/composables/useCellPanelPayload'
import CellMarkdownBlock from '@/components/notebooks/cell/preview/CellMarkdownBlock.vue'

const props = defineProps<{ slug: string }>()

const flowStore = useFlowStore()
const toast = useToast()

const doc = ref('')

const { isLoading } = useCellPanelPayload({
  slug: () => props.slug,
  follows: (cell) => cell.changed_step,
  fetch: () => flowStore.fetchCellNote(props.slug),
  onLoaded: (loaded) => {
    doc.value = loaded
  },
  onFailed: (error) => toast.add(errorToast(error, 'Failed to load note')),
})
</script>

<style scoped>
.note {
  font-size: 14px;
}
</style>
