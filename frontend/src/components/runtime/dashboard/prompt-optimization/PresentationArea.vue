<template>
  <div class="presentation">
    <VueFlow
      :nodes="initialNodes"
      class="basic-flow"
      :default-viewport="{ zoom: 1 }"
      :min-zoom="0.2"
      :max-zoom="4"
    >
      <template #node-custom="props">
        <custom-node :id="props.id" :data="props.data" />
      </template>
      <template #edge-custom="edgeProps">
        <custom-edge v-bind="edgeProps" />
      </template>
      <Background pattern-color="var(--dots-color)" />
    </VueFlow>
    <PresentationAreaToolbar class="toolbar"></PresentationAreaToolbar>
  </div>
</template>

<script setup lang="ts">
import type { PromptNode } from '@/components/express-tasks/prompt-fusion/interfaces'
import { useVueFlow, VueFlow, type Edge } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import { onMounted } from 'vue'
import CustomNode from '@/components/express-tasks/prompt-fusion/step-main/nodes/CustomNode.vue'
import CustomEdge from '@/components/ui/vue-flow/CustomEdge.vue'
import PresentationAreaToolbar from './PresentationAreaToolbar.vue'

type Props = {
  initialNodes: PromptNode[]
  initialEdges: Edge[]
}

const props = defineProps<Props>()

const { addEdges } = useVueFlow()

onMounted(() => {
  addEdges(props.initialEdges)
})
</script>

<style scoped>
.basic-flow {
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: var(--p-border-radius-lg);
  --dots-color: #cdcddb;
}

[data-theme='dark'] .basic-flow {
  --dots-color: rgba(69, 69, 74, 0.7);
}

.presentation {
  position: relative;
}
</style>
