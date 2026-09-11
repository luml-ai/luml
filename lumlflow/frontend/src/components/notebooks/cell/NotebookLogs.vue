<template>
  <p v-if="isLoading" class="text-sm text-muted-color">Loading logs…</p>
  <pre v-else-if="renderedLogs" class="log-output nowheel">{{ renderedLogs }}</pre>
  <p v-else class="text-sm text-muted-color">No logs yet</p>
</template>

<script setup lang="ts">
import type { NotebookLogsProps } from '@/components/notebooks/cell/cell.interface'
import { computed, onBeforeMount, ref } from 'vue'
import { useToast } from 'primevue/usetoast'
import { errorToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { terminalText } from '@/utils/terminal'

const props = defineProps<NotebookLogsProps>()

const flowStore = useFlowStore()
const toast = useToast()

const logs = ref<string | null>(null)
const isLoading = ref(false)

onBeforeMount(async () => {
  isLoading.value = true
  try {
    logs.value = await flowStore.fetchCellLogs(props.slug)
  } catch (error) {
    toast.add(errorToast(error, 'Failed to load logs'))
  } finally {
    isLoading.value = false
  }
})

const renderedLogs = computed(() => terminalText(logs.value ?? '').trimEnd())
</script>

<style scoped>
@reference "@/assets/css/index.css";

.log-output {
  @apply max-h-64 overflow-auto whitespace-pre-wrap wrap-break-word rounded-lg border border-surface bg-surface-50 dark:bg-surface-900 p-3 font-mono text-sm leading-relaxed;
}
</style>
