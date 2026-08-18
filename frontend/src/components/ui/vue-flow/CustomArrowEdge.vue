<template>
  <base-edge
    :path="path[0]"
    :marker-start="`url(#${markerId}-arrow)`"
    :marker-end="`url(#${markerId})`"
  />
  <custom-arrow-marker
    :id="markerId"
    :stroke="markerColor"
    :fill="markerColor"
    :arrow-fill="arrowFill"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { BaseEdge, getSmoothStepPath, type EdgeProps } from '@vue-flow/core'
import { useVueFlow } from '@vue-flow/core'
import CustomArrowMarker from './CustomArrowMarker.vue'

const { findNode, getSelectedEdges } = useVueFlow()

const props = defineProps<EdgeProps>()

const path = computed(() => getSmoothStepPath({ ...props, borderRadius: 6 }))
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
const arrowFill = computed(() =>
  isEdgeSelected.value ? 'var(--p-primary-color)' : 'var(--vue-flow-edge-path-color)',
)
</script>

<style scoped></style>
