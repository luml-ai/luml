<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <RouterLink :to="backTarget" class="toolbar-back-button">
        <ChevronLeft :size="14" />
      </RouterLink>
      <div class="toolbar-title">
        <span
          class="status-circle"
          :class="`status-circle--${statusSeverity}`"
          v-tooltip.bottom="statusTooltip"
        ></span>
        <span>{{ flowName }}</span>
        <span>/</span>
        <span>{{ branchName }}</span>
      </div>
      <NotebookPairAgent />
    </div>
    <div class="toolbar-right">
      <SelectButton
        :model-value="flowStore.viewMode"
        :options="NOTEBOOK_VIEW_MODE_OPTIONS"
        :allow-empty="false"
        optionLabel="label"
        optionValue="value"
        aria-labelledby="basic"
        size="small"
        @update:model-value="flowStore.setViewMode($event)"
      />
      <Button
        v-tooltip.bottom="kernelTooltip"
        variant="outlined"
        severity="secondary"
        size="small"
        class="kernel-button"
        :class="{ 'kernel-button--running': flowStore.kernelState === 'running' }"
        :aria-label="kernelTooltip"
        :loading="flowStore.isKernelRestarting"
        @click="restartKernel"
      >
        <template #icon> <RotateCcw :size="12" /> </template>
      </Button>
      <NotebookSettings />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { NotebookHealthState } from '@/components/notebooks/notebooks.interface'
import { ChevronLeft, RotateCcw } from 'lucide-vue-next'
import { Button, SelectButton, useToast } from 'primevue'
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import { ROUTE_NAMES } from '@/router/router.const'
import { useFlowStore } from '@/store/flow'
import { baseName, parentDirectory } from '@/helpers/path'
import {
  NOTEBOOK_HEALTH_LABELS,
  NOTEBOOK_HEALTH_SEVERITY,
  NOTEBOOK_VIEW_MODE_OPTIONS,
} from '@/components/notebooks/notebooks.const'
import NotebookPairAgent from '@/components/notebooks/NotebookPairAgent.vue'
import NotebookSettings from '@/components/notebooks/NotebookSettings.vue'
import { errorToast } from '@/toasts'

const flowStore = useFlowStore()
const toast = useToast()

const kernelTooltip = computed(() =>
  flowStore.kernelState ? `Kernel ${flowStore.kernelState} · Restart` : 'Restart kernel',
)

async function restartKernel() {
  try {
    await flowStore.restartKernel()
  } catch (error) {
    toast.add(errorToast(error))
  }
}

const backTarget = computed(() => {
  const flow = flowStore.currentFlow
  const directory = flow ? parentDirectory(flow) : null

  return {
    name: ROUTE_NAMES.WORKSPACES,
    query: directory ? { directory } : {},
  }
})

const flowName = computed(() => {
  const flow = flowStore.currentFlow
  return flow ? baseName(flow) : ''
})

const branchName = computed(() => flowStore.currentBranch?.branch ?? '')

const notebookHealth = computed<NotebookHealthState>(() => {
  const cells = flowStore.cells
  if (cells.length === 0) return 'empty'
  if (cells.some((cell) => cell.state === 'failed')) return 'failed'
  if (cells.some((cell) => cell.state === 'unsynced')) return 'unsynced'
  if (cells.some((cell) => cell.state === 'unmaterialized')) return 'unmaterialized'
  return 'synced'
})

const statusSeverity = computed(() => NOTEBOOK_HEALTH_SEVERITY[notebookHealth.value])
const statusTooltip = computed(() => NOTEBOOK_HEALTH_LABELS[notebookHealth.value])
</script>

<style scoped>
@reference "@/assets/css/index.css";

.toolbar {
  @apply flex items-center justify-between gap-5 py-2.5 px-5 bg-(--p-card-background) border border-surface rounded-lg;
}
.toolbar-left {
  @apply flex items-center gap-4;
}
.toolbar-back-button {
  @apply cursor-pointer shrink-0 hover:text-primary-600 transition-colors;
}
.status-circle {
  @apply w-5 h-5 shrink-0 rounded-full border flex items-center justify-center;
}
.status-circle::before {
  @apply content-[''] w-3 h-3 rounded-full;
}
.status-circle--success {
  @apply bg-(--p-toast-success-background) border-(--p-toast-success-border-color);
}
.status-circle--success::before {
  @apply bg-(--p-badge-success-background) shadow-[0px_2px_8px_0px_#22C55E80];
}
.status-circle--warn {
  @apply bg-(--p-toast-warn-background) border-(--p-toast-warn-border-color);
}
.status-circle--warn::before {
  @apply bg-(--p-badge-warn-background) shadow-[0px_2px_8px_0px_#F9731680];
}
.status-circle--info {
  @apply bg-(--p-toast-info-background) border-(--p-toast-info-border-color);
}
.status-circle--info::before {
  @apply bg-(--p-badge-info-background) shadow-[0px_2px_8px_0px_#0EA5E980];
}
.status-circle--danger {
  @apply bg-(--p-toast-error-background) border-(--p-toast-error-border-color);
}
.status-circle--danger::before {
  @apply bg-(--p-badge-danger-background) shadow-[0px_2px_8px_0px_#EF444480];
}
.status-circle--secondary {
  @apply bg-(--p-toast-secondary-background) border-(--p-toast-secondary-border-color);
}
.status-circle--secondary::before {
  @apply bg-(--p-badge-secondary-background);
}
.toolbar-title {
  @apply flex items-center gap-2;
}
.kernel-button {
  @apply p-0 h-10! w-10! text-muted-color!;
}
.kernel-button--running {
  @apply text-(--p-badge-success-background)!;
}
.toolbar-right {
  @apply flex gap-4;
}
</style>
