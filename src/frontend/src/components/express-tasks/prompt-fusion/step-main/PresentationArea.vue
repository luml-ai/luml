<template>
  <VueFlow
    :nodes="initialNodes"
    class="basic-flow"
    :default-viewport="{ zoom: 1 }"
    :min-zoom="0.2"
    :max-zoom="4"
    :isValidConnection="isValidConnection"
  >
    <template #node-custom="props">
      <custom-node
        :id="props.id"
        :data="props.data"
        @duplicate="duplicateNode(props.id)"
        @delete="removeNodes(props.id)"
      />
    </template>
    <template #edge-custom="edgeProps">
      <custom-edge v-bind="edgeProps" />
    </template>
    <Background pattern-color="var(--dots-color)" />
  </VueFlow>
</template>

<script setup lang="ts">
import type { NodeField, PromptNode } from '../interfaces'
import { VueFlow, useVueFlow, type Connection } from '@vue-flow/core'
import CustomNode from './nodes/CustomNode.vue'
import { v4 as uuidv4 } from 'uuid'
import { Background } from '@vue-flow/background'
import { onBeforeMount, onBeforeUnmount } from 'vue'
import CustomEdge from '@/components/ui/vue-flow/CustomEdge.vue'

type Props = {
  initialNodes: PromptNode[]
}

defineProps<Props>()

const { nodes, onConnect, addEdges, removeNodes, addNodes, removeEdges, getSelectedEdges } =
  useVueFlow()

function duplicateNode(id: string) {
  const node = nodes.value.find((node) => node.id === id)
  if (!node) throw new Error('Node not found')
  const clone: PromptNode = JSON.parse(JSON.stringify(node))
  clone.id = uuidv4()
  clone.data.fields = clone.data.fields.map((field) => ({ ...field, id: uuidv4() }))
  clone.position.x = 10
  clone.position.y = 10
  clone.selected = false
  addNodes(clone)
}
function isValidConnection(connection: Connection) {
  if (connection.source === connection.target) return false
  const sourceNode = nodes.value.find((node) => node.id === connection.source)
  const targetNode = nodes.value.find((node) => node.id === connection.target)
  const sourceField = sourceNode?.data.fields.find(
    (field: NodeField) => field.id === connection.sourceHandle,
  )
  const targetField = targetNode?.data.fields.find(
    (field: NodeField) => field.id === connection.targetHandle,
  )
  if (sourceField?.handlePosition === targetField?.handlePosition) return false
  return true
}
function onBackspaceClick(e: KeyboardEvent) {
  if (e.code === 'Delete') {
    removeEdges(getSelectedEdges.value)
  }
}

onConnect((connection) => {
  addEdges({ ...connection, type: 'custom' })
})

onBeforeMount(() => {
  document.addEventListener('keydown', onBackspaceClick)
})
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onBackspaceClick)
})
</script>

<style scoped>
.basic-flow {
  --dots-color: #cdcddb;

  height: calc(100% + 31px);
}

[data-theme='dark'] .basic-flow {
  --dots-color: rgba(69, 69, 74, 0.7);
}
</style>
