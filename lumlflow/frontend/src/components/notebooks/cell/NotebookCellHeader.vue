<template>
  <header class="header">
    <div class="header-left overflow-hidden">
      <component
        :is="NOTEBOOK_ASSET_ICONS['graph']"
        :size="14"
        color="var(--p-button-text-secondary-color)"
        class="mt-1 shrink-0"
      />
      <div class="overflow-hidden">
        <h3 class="mb-1 truncate">correlation_heatmap</h3>
        <div class="text-sm text-muted-color">8.5s</div>
      </div>
    </div>
    <div class="header-right shrink-0">
      <Button
        variant="outlined"
        severity="secondary"
        class="p-0 w-10 h-10"
        aria-haspopup="menu"
        @click="menu?.toggle($event)"
      >
        <template #icon>
          <EllipsisVertical :size="14" />
        </template>
      </Button>
      <Menu ref="menu" :model="menuItems" popup :pt="MENU_PT">
        <template #itemicon="{ item }">
          <component :is="(item as CellHeaderMenuItem).glyph" :size="14" class="shrink-0" />
        </template>
      </Menu>
    </div>
  </header>
</template>

<script setup lang="ts">
import type { MenuItem } from 'primevue/menuitem'
import type { LucideIcon } from 'lucide-vue-next'
import { Button, Menu, type MenuPassThroughOptions } from 'primevue'
import { useTemplateRef } from 'vue'
import { NOTEBOOK_ASSET_ICONS } from '../notebooks.const'
import {
  CloudUpload,
  Copy,
  Download,
  EllipsisVertical,
  Maximize2,
  Notebook,
  Pencil,
  Plus,
  Send,
  Trash2,
} from 'lucide-vue-next'

const MENU_PT: MenuPassThroughOptions = {
  root: {
    style: 'background-color: var(--p-card-background);',
  },
}

type CellHeaderMenuItem = MenuItem & { glyph?: LucideIcon }

const menu = useTemplateRef<InstanceType<typeof Menu>>('menu')

const menuItems: CellHeaderMenuItem[] = [
  { label: 'Expand', glyph: Maximize2, command: () => console.log('Expand') },
  { label: 'Rename', glyph: Pencil, command: () => console.log('Rename') },
  { label: 'Duplicate', glyph: Copy, command: () => console.log('Duplicate') },
  {
    label: 'Add cell downstream',
    glyph: Plus,
    command: () => console.log('Add cell downstream'),
  },
  { label: 'Go to Notebook', glyph: Notebook, command: () => console.log('Go to Notebook') },
  { separator: true },
  { label: 'Send to agent', glyph: Send, command: () => console.log('Send to agent') },
  { label: 'Promote to LUML', glyph: CloudUpload, command: () => console.log('Promote to LUML') },
  { label: 'Download', glyph: Download, command: () => console.log('Download') },
  { separator: true },
  {
    label: 'Delete from this lane',
    glyph: Trash2,
    class: 'notebook-cell-menu-danger',
    command: () => console.log('Delete from this lane'),
  },
]
</script>

<style scoped>
@reference "@/assets/css/index.css";

.header {
  @apply flex items-center justify-between gap-4;
}
.header-left {
  @apply flex items-start gap-1;
}
</style>

<style>
.notebook-cell-menu-danger .p-menu-item-content {
  color: var(--p-button-text-warn-color);
}
</style>
