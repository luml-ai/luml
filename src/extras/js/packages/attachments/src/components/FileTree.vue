<template>
  <div class="file-tree">
    <ul>
      <FileNode
        v-for="node in tree"
        :key="node.path || node.name"
        :node="node"
        :selected="selected"
        @select="onSelect"
      />
    </ul>
  </div>
</template>

<script setup lang="ts">
import FileNode from './FileNode.vue'
import type { FileNode as FileNodeType, FileNodeEmits } from '../interfaces/interfaces'

defineProps<{
  tree: FileNodeType[]
  selected: FileNodeType | null
}>()

const emit = defineEmits<FileNodeEmits>()

function onSelect(node: FileNodeType) {
  emit('select', node)
}
</script>

<style scoped>
.file-tree {
  width: 250px;
  overflow-y: auto;
  padding: 8px;
  overflow-x: auto;
  border-right: 1px solid var(--p-divider-border-color);
}
</style>
