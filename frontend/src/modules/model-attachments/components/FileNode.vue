<template>
  <li>
    <div class="node" :class="{ selected: isSelected }" @click.stop="handleClick">
      <ChevronDown
        v-if="node.type === 'folder'"
        :class="{ rotated: isExpanded }"
        class="arrow-icon"
      />
      <component :is="fileIcon" class="node-icon" />
      <span class="node-name">{{ node.name }}</span>
    </div>

    <ul v-if="node.type === 'folder' && isExpanded">
      <FileNode
        v-for="child in node.children"
        :key="child.path || child.name"
        :node="child"
        :selected="selected"
        @select="handleSelect"
      />
    </ul>
  </li>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Component } from 'vue'
import {
  Folder,
  File,
  FileText,
  FileMusic,
  FileVideo,
  FileImage,
  FileCode,
  ChevronDown,
} from 'lucide-vue-next'
import { getFileType, type FileType } from '../utils/fileTypes'
import type {
  FileNode as FileNodeType,
  FileNodeProps,
  FileNodeEmits,
} from '../interfaces/interfaces'

const FILE_TYPE_ICONS: Record<FileType, Component> = {
  image: FileImage,
  svg: FileImage,
  audio: FileMusic,
  video: FileVideo,
  pdf: FileText,
  text: FileText,
  table: FileText,
  code: FileCode,
  html: FileCode,
}

const props = defineProps<FileNodeProps>()
const emit = defineEmits<FileNodeEmits>()

const isExpanded = ref(false)

const isSelected = computed(() => {
  return props.selected?.path === props.node.path
})

const fileIcon = computed((): Component => {
  if (props.node.type === 'folder') {
    return Folder
  }

  const fileType = getFileType(props.node.name)
  return fileType ? FILE_TYPE_ICONS[fileType] : File
})

function handleClick(): void {
  if (props.node.type === 'file') {
    emit('select', props.node)
  } else {
    isExpanded.value = !isExpanded.value
  }
}

function handleSelect(node: FileNodeType): void {
  emit('select', node)
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
