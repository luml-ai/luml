<template>
  <div class="toolbar">
    <div class="toolbar-left">
      <button class="toolbar-back-button">
        <ChevronLeft :size="14" />
      </button>
      <div class="toolbar-title">
        <span class="status-circle"></span>
        <span>churn.flow</span>
        <span>/</span>
        <span>Test-1</span>
      </div>
      <Tag value="Unpaired" severity="secondary" />
      <button class="toolbar-pair-button">Pair an agent</button>
    </div>
    <div class="toolbar-right">
      <SelectButton
        v-model="selectedOption"
        :options="options"
        optionLabel="label"
        optionValue="value"
        aria-labelledby="basic"
        size="small"
      />
      <Button variant="outlined" severity="secondary" size="small" class="toolbar-settings-button">
        <template #icon> <Bolt :size="12" /> </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Bolt, ChevronLeft, Notebook, Workflow } from 'lucide-vue-next'
import { Button, SelectButton, Tag } from 'primevue'
import { ref } from 'vue'

const options = [
  {
    label: 'Canvas',
    value: 'canvas',
    icon: Workflow,
  },
  {
    label: 'Notebook',
    value: 'notebook',
    icon: Notebook,
  },
]

const selectedOption = ref('canvas')
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
  @apply w-5 h-5 shrink-0 rounded-full bg-(--p-toast-success-background) border border-(--p-toast-success-border-color) flex items-center justify-center;
}
.status-circle::before {
  @apply content-[''] w-3 h-3 rounded-full bg-(--p-badge-success-background) shadow-[0px_2px_8px_0px_#22C55E80];
}
.toolbar-title {
  @apply flex items-center gap-2;
}
.toolbar-pair-button {
  @apply text-primary cursor-pointer hover:text-primary-600 transition-colors;
}
.toolbar-right {
  @apply flex gap-4;
}
.toolbar-settings-button {
  @apply p-0;
}
</style>
