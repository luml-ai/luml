<template>
  <div class="file-tree">
    <ul>
      <TreeNode
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
import TreeNode from './FileNode.vue'
import { defineProps, defineEmits } from 'vue'

const props = defineProps<{
  tree: any[]
  selected: any
}>()

const emit = defineEmits<{ (e: 'select', node: any): void }>()

function onSelect(node: any) {
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
