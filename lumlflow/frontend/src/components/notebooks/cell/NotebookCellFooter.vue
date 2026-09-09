<template>
  <footer class="footer">
    <div class="footer-left">
      <component :is="stateIcon" :size="14" color="var(--p-button-text-secondary-color)" class="mt-1" />
      <div>
        <h3 class="mb-1">{{ stateLabel }}</h3>
        <div v-if="subtitle" class="text-sm text-muted-color">{{ subtitle }}</div>
      </div>
    </div>
    <div class="footer-right">
      <Button v-if="state !== 'synced'" variant="outlined" severity="secondary" class="p-0 w-10 h-10">
        <template #icon>
          <Play :size="14" />
        </template>
      </Button>
    </div>
  </footer>
</template>

<script setup lang="ts">
import type { NotebookCellFooterProps } from '@/components/notebooks/cell/cell.interface'
import { computed } from 'vue'
import { Play } from 'lucide-vue-next'
import { Button } from 'primevue'
import { CELL_STATE_ICONS, CELL_STATE_LABELS } from '@/components/notebooks/cell/cell.const'

const props = defineProps<NotebookCellFooterProps>()

const stateLabel = computed(() => CELL_STATE_LABELS[props.state])
const stateIcon = computed(() => CELL_STATE_ICONS[props.state])
const subtitle = computed(() => {
  if (props.causes.length > 0) return props.causes.join(' · ')
  return props.reused ? 'Reused from cache' : ''
})
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
