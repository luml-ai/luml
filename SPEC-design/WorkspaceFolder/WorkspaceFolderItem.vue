<template>
  <div
    v-if="item.type === 'file' || item.type === 'folder'"
    class="item"
    :class="{ 'item-selected': selected, 'item-menu-open': menuOpen }"
  >
    <div class="item-main-info muted-emphasis">
      <component :is="item.type === 'folder' ? Folder : fileIcon(item.name)" :size="16" class="item-icon" />
      <div v-if="renaming" class="rename-block">
        <InputText :model-value="renameValue" class="rename-input" />
        <Button label="Save" severity="secondary" size="small" class="save-button" />
      </div>
      <span v-else class="item-name">{{ item.name }}</span>
    </div>
    <div class="item-side">
      <span v-if="item.type === 'file'" class="item-size">{{ getSizeText(item.size) }}</span>
      <FlowStateMarker
        v-else-if="openBeneath.length"
        :kernel="openBeneath.some((flow) => flow.kernel === 'running') ? 'running' : 'stopped'"
        :flows="openBeneath.length"
        :agents="openBeneath.reduce((sum, flow) => sum + flow.leased_sessions, 0)"
      />
      <!-- product:PROP-004 B-14: the ⋮ menu the notebook rows have, for files and folders. -->
      <div class="menu-anchor">
        <Button severity="secondary" variant="text" aria-haspopup="menu" @click.stop="menu?.toggle($event)">
          <template #icon>
            <EllipsisVertical :size="16" />
          </template>
        </Button>
        <Menu ref="menu" :model="menuItems" popup />
        <!-- The app opens the popup Menu above on click; a story pins it open below the button. -->
        <div v-if="menuOpen" class="menu-open">
          <Menu :model="menuItems" />
        </div>
      </div>
    </div>
  </div>
  <WorkspaceFolderItemFlow
    v-else-if="item.type === 'flow'"
    :item="item"
    :open-flow="openFlows.find((flow) => flow.path === item.path) ?? null"
    :menu-open="menuOpen"
    :renaming="renaming"
    :rename-value="renameValue"
  />
</template>

<script setup lang="ts">
import { computed, useTemplateRef } from 'vue'
import {
  EllipsisVertical,
  File,
  FileAudio,
  FileCode,
  FileImage,
  FileText,
  FileVideo,
  Folder,
  Package,
  Sheet,
} from 'lucide-vue-next'
import { Button, InputText, Menu, type MenuItem } from '@/ui'
import FlowStateMarker from '@/components/FlowStateMarker/FlowStateMarker.vue'
import type { OpenFlow } from '@/components/FlowStateMarker/openFlows'
import type { WorkspaceFolderItem } from '@/blocks/WorkspaceFolder/interface'
import WorkspaceFolderItemFlow from '@/blocks/WorkspaceFolder/WorkspaceFolderItemFlow.vue'

type Props = {
  item: WorkspaceFolderItem
  openFlows: OpenFlow[]
  menuOpen?: boolean
  renaming?: boolean
  renameValue?: string
  /** UIP-002: the file whose preview is open. */
  selected?: boolean
}

const props = defineProps<Props>()

const menu = useTemplateRef<InstanceType<typeof Menu>>('menu')

// B-14: rename, move and delete; "Duplicate" stays notebook-only.
const menuItems: MenuItem[] = [{ label: 'Rename' }, { label: 'Move to…' }, { label: 'Delete' }]

const openBeneath = computed(() =>
  props.openFlows.filter((flow) => {
    const [folder, ...rest] = (flow.relative_path ?? '').split('/').filter(Boolean)
    return flow.inside && folder === props.item.name && rest.length > 0
  }),
)

// UIP-002: the icon follows the preview type, as in the attachments file tree (utils/fileTypes.ts);
// `.luml` packages get their own (product:PROP-004 B-09 – B-11).
function fileIcon(name: string) {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'luml') return Package
  if (['py', 'js', 'ts', 'yaml', 'yml', 'json', 'html'].includes(ext)) return FileCode
  if (['csv', 'xml', 'parquet'].includes(ext)) return Sheet
  if (['png', 'jpg', 'jpeg', 'svg'].includes(ext)) return FileImage
  if (['mp3', 'wav', 'ogg'].includes(ext)) return FileAudio
  if (['mp4', 'webm', 'ogv'].includes(ext)) return FileVideo
  if (['txt', 'md', 'pdf'].includes(ext)) return FileText
  return File
}

function getSizeText(size: number): string {
  if (size < 1000) return `${size}B`
  if (size < 1000000) return `${size / 1000}KB`
  if (size < 1000000000) return `${size / 1000000}MB`
  return `${size / 1000000000}GB`
}
</script>

<style scoped>
.item {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  height: 3.125rem;
  padding: 0.25rem 0.5rem;
  border-bottom: 1px solid var(--p-datatable-body-cell-border-color);
  cursor: pointer;
  transition: background-color 0.15s;
}

.item-menu-open {
  z-index: 30;
}

.item:last-child {
  border-bottom-width: 0;
}

.muted-emphasis {
  color: var(--p-text-hover-muted-color);
}

.item-main-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  overflow: hidden;
}

.item-side {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-shrink: 0;
}

.item-icon,
.item-size {
  flex-shrink: 0;
}

.item-size {
  color: var(--p-text-muted-color);
  font-size: 0.875rem;
}

.item-name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item:hover {
  background-color: var(--p-list-option-focus-background);
  border-radius: 8px;
}

/* UIP-002: the open file keeps the fill the attachments tree gives the selected file. */
.item.item-selected {
  background-color: var(--p-menu-item-focus-background);
  border-radius: 8px;
}

/* As WorkspaceFolderItemFlow.vue. */
.rename-block {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.rename-input {
  max-width: 12.5rem;
  max-height: 1.625rem;
  padding-left: 0 !important;
  padding-right: 0 !important;
  border-radius: 0 !important;
  border-top-width: 0 !important;
  border-left-width: 0 !important;
  border-right-width: 0 !important;
  box-shadow: none !important;
}

/* Smaller than the notebook row's Save (core team input, review 2026-11-09). */
.save-button {
  max-height: 1.75rem;
  padding-top: 0.25rem;
  padding-bottom: 0.25rem;
}

.menu-anchor {
  position: relative;
  flex-shrink: 0;
}

.menu-open {
  position: absolute;
  top: calc(100% + 2px);
  right: 0;
  z-index: 20;
  border-radius: var(--p-border-radius-md);
  box-shadow: var(--p-overlay-popover-shadow);
}
</style>
