<template>
  <footer class="footer">
    <div class="footer-left">
      <component
        :is="stateIcon"
        :size="14"
        color="var(--p-button-text-secondary-color)"
        class="mt-1"
      />
      <div>
        <h3 class="mb-1">{{ stateLabel }}</h3>
        <div v-if="subtitle" class="text-sm text-muted-color">{{ subtitle }}</div>
      </div>
    </div>
    <div class="footer-right">
      <Button
        v-if="state !== 'synced'"
        variant="outlined"
        severity="secondary"
        class="p-0 w-10 h-10"
        :loading="isRunning"
        :disabled="isRunning"
        @click="onRunCell"
      >
        <template #icon>
          <Play :size="14" />
        </template>
      </Button>
    </div>
  </footer>
</template>

<script setup lang="ts">
import type { NotebookCellFooterProps } from '@/components/notebooks/cell/cell.interface'
import { computed, ref } from 'vue'
import { Play } from 'lucide-vue-next'
import { Button } from 'primevue'
import { useToast } from 'primevue/usetoast'
import { errorToast, successToast } from '@/toasts'
import { useFlowStore } from '@/store/flow'
import { CELL_STATE_ICONS, CELL_STATE_LABELS } from '@/components/notebooks/cell/cell.const'

const props = defineProps<NotebookCellFooterProps>()

const toast = useToast()
const flowStore = useFlowStore()

const stateLabel = computed(() => CELL_STATE_LABELS[props.state])
const stateIcon = computed(() => CELL_STATE_ICONS[props.state])
const subtitle = computed(() => {
  if (props.causes.length > 0) return props.causes.join(' · ')
  return props.reused ? 'Reused from cache' : ''
})

const isRunning = ref(false)

async function onRunCell() {
  isRunning.value = true
  try {
    const result = await flowStore.runCell(props.cell.slug)
    if (result.failed) {
      toast.add(errorToast(new Error(`\`${result.failed}\` failed to run`), 'Run failed'))
    } else {
      toast.add(successToast(`\`${props.cell.slug}\` is up to date`))
    }
  } catch (error) {
    toast.add(errorToast(error, 'Failed to run cell'))
  } finally {
    isRunning.value = false
  }
}
</script>

<style scoped>
@reference "@/assets/css/index.css";

.footer {
  @apply flex items-center justify-between gap-4;
}
.footer-left {
  @apply flex items-start gap-1;
}
</style>
