<template>
  <li>
    <div class="node" :class="{ selected: selected?.path === node.path }" @click.stop="handleClick">
      <ChevronDown v-if="node.type === 'folder'" :class="{ rotated: toggle }" class="arrow-icon" />
      <component :is="fileIcon" class="node-icon" />
      <span class="node-name">{{ node.name }}</span>
    </div>
    <ul v-if="node.type === 'folder' && toggle">
      <FileNode
        v-for="child in node.children"
        :key="child.path || child.name"
        :node="child"
        :selected="selected"
        @select="$emit('select', $event)"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import {
  Folder,
  File,
  FileText,
  FileMusic,
  FileVideo,
  FileImage,
  ChevronDown,
  FileCode,
} from 'lucide-vue-next'
import { getFileType } from './utils/fileTypes'

const props = defineProps<{ node: any; selected: any }>()
const emit = defineEmits<{ (e: 'select', node: any): void }>()

const toggle = ref(false)

const fileIcon = computed(() => {
  if (props.node.type === 'folder') return Folder
  const fileType = getFileType(props.node.name)
  switch (fileType) {
    case 'image':
      return FileImage
    case 'audio':
      return FileMusic
    case 'video':
      return FileVideo
    case 'pdf':
      return FileText
    case 'text':
      return FileText
    case 'code':
      return FileCode
    case 'table':
      return FileText
    case 'html':
      return FileCode
    default:
      return File
  }
})

function handleClick() {
  if (props.node.type === 'file') {
    emit('select', props.node)
  } else {
    toggle.value = !toggle.value
  }
}
</script>

<style scoped>
.node {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  cursor: pointer;
  border-radius: 8px;
  min-width: 100%;
  width: max-content;
  box-sizing: border-box;
}

.node-icon {
  width: 14px;
  height: 14px;
  flex-shrink: 0;
}

.arrow-icon {
  width: 14px;
  height: 14px;
  transition: transform 0.2s;
  transform: rotate(-90deg);
}

.arrow-icon.rotated {
  transform: rotate(0deg);
}

.node-name {
  white-space: nowrap;
  overflow: hidden;
}

.node:hover,
.node.selected {
  background-color: var(--p-menu-item-focus-background);
}

ul {
  padding-left: 21px;
  list-style: none;
  margin: 0;
}

li {
  list-style: none;
}
</style>
