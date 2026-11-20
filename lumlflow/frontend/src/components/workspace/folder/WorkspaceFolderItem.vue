<template>
  <div class="item" :class="{ selected, renaming }">
    <div class="item-main">
      <component
        :is="icon"
        :size="16"
        class="shrink-0"
        :class="{ 'text-(--p-tabs-tab-active-color)': item.type === 'flow' }"
      />
      <InlineRename
        v-if="renaming"
        :item="item"
        :busy="busy"
        @save="emit('rename', $event)"
        @cancel="emit('cancel')"
      />
      <RouterLink
        v-else-if="item.type === 'flow'"
        :to="{ name: ROUTE_NAMES.WORKSPACE_FLOW, query: { directory: item.path } }"
        class="row-link"
      >
        {{ item.name }}
      </RouterLink>
      <button
        v-else
        type="button"
        class="row-link"
        :aria-current="selected || undefined"
        @click="emit('open', item)"
      >
        {{ item.name }}
      </button>
      <span v-if="item.is_symlink" title="Symbolic link" aria-label="Symbolic link"
        ><Link2 :size="13"
      /></span>
    </div>
    <div class="flex items-center gap-3 shrink-0">
      <span v-if="item.type === 'file'" class="text-sm text-muted-color">
        {{ item.size === null ? '—' : getSizeText(item.size) }}
      </span>
      <time
        v-if="item.type === 'file' && item.modified_at"
        :datetime="item.modified_at"
        class="text-sm text-muted-color"
        :class="{ 'sr-only': compact }"
        :title="item.modified_at"
      >
        {{ dateToText(item.modified_at) }}
      </time>
      <FlowStateMarker
        v-if="openFlow"
        :kernel="openFlow.kernel"
        :label="openFlow.active_runs"
        :agents="openFlow.leased_sessions"
        :last-activity="openFlow.last_activity"
        class="relative"
      />
      <FlowStateMarker
        v-else-if="openBeneath.length"
        class="relative"
        :kernel="openBeneath.some((flow) => flow.kernel === 'running') ? 'running' : 'stopped'"
        :flows="openBeneath.length"
        :agents="openBeneath.reduce((sum, flow) => sum + flow.leased_sessions, 0)"
      />
      <Button
        severity="secondary"
        variant="text"
        class="relative"
        :aria-label="`Actions for ${item.name}`"
        aria-haspopup="menu"
        :disabled="busy"
        @click="emit('menu', $event, item)"
      >
        <template #icon><EllipsisVertical :size="16" /></template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Button } from 'primevue'
import { getFileExtension, getFileType } from '@luml/attachments'
import {
  EllipsisVertical,
  File,
  FileAudio,
  FileCode,
  FileCodeCorner,
  FileImage,
  FileText,
  FileVideo,
  Folder,
  Link2,
  Package,
  Sheet,
} from 'lucide-vue-next'
import { dateToText } from '@/helpers/date'
import { getSizeText } from '@/helpers/string'
import { ROUTE_NAMES } from '@/router/router.const'
import { useWorkspaceStore } from '@/store/workspace'
import FlowStateMarker from '@/components/workspace/FlowStateMarker.vue'
import InlineRename from './InlineRename.vue'
import type { IWorkspaceFolderItem } from './interface'

const props = defineProps<{
  item: IWorkspaceFolderItem
  selected?: boolean
  compact?: boolean
  renaming?: boolean
  busy?: boolean
}>()
const emit = defineEmits<{
  open: [item: IWorkspaceFolderItem]
  menu: [event: MouseEvent, item: IWorkspaceFolderItem]
  rename: [name: string]
  cancel: []
}>()
const store = useWorkspaceStore()
const openFlow = computed(
  () => props.item.type === 'flow' && store.openFlowsByPath.get(props.item.path),
)
const openBeneath = computed(() =>
  props.item.type === 'folder' ? (store.openFlowsByFolder.get(props.item.path) ?? []) : [],
)
const icons = {
  image: FileImage,
  svg: FileImage,
  audio: FileAudio,
  video: FileVideo,
  code: FileCode,
  html: FileCode,
  table: Sheet,
  pdf: FileText,
  text: FileText,
}
const icon = computed(() => {
  const { type, name } = props.item
  if (type === 'folder') return Folder
  if (type === 'flow') return FileCodeCorner
  const extension = getFileExtension(name)
  if (extension === 'luml') return Package
  if (extension === 'json') return FileCode
  const previewType = getFileType(name)
  return previewType ? icons[previewType] : File
})
</script>

<style scoped>
@reference "@/assets/css/index.css";
.item {
  @apply relative border-b border-(--p-datatable-body-cell-border-color) last:border-b-0 py-1 px-2 min-h-12.5 flex items-center justify-between gap-3;
}
.item-main {
  @apply flex items-center gap-2 min-w-0 text-muted-color-emphasis;
}
.row-link {
  @apply truncate text-start cursor-pointer;
}
.row-link::after {
  content: '';
  position: absolute;
  inset: 0;
}
.item:has(.row-link:hover),
.item:has(.row-link:focus-visible) {
  @apply rounded-lg bg-(--p-list-option-focus-background);
}
.item.selected {
  @apply rounded-lg bg-(--p-menu-item-focus-background);
}
</style>
