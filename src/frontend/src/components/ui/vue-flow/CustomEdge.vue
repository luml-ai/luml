<template>
  <base-edge
    :path="path[0]"
    :marker-end="`url(#${markerId})`"
    :marker-start="`url(#${markerId})`"
  />
  <custom-marker :id="markerId" :stroke="markerColor" :fill="markerColor" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BaseEdge, getBezierPath, type EdgeProps } from '@vue-flow/core'
import CustomMarker from './CustomMarker.vue'
import { useVueFlow } from '@vue-flow/core'

const { findNode, getSelectedEdges } = useVueFlow()

const props = defineProps<EdgeProps>()

const path = computed(() => getBezierPath(props))
const markerId = computed(() => `${props.id}-marker`)
const isEdgeSelected = computed(() => getSelectedEdges.value.find((edge) => edge.id === props.id))
const isNodesSelected = computed(() => {
  const sourceNode = findNode(props.source)
  const targetNode = findNode(props.target)
  return (sourceNode && sourceNode.selected) || (targetNode && targetNode.selected)
})
const markerColor = computed(() =>
  isEdgeSelected.value || isNodesSelected.value ? 'var(--p-primary-color)' : 'var(--p-surface-500)',
)
</script>

<style scoped></style>
