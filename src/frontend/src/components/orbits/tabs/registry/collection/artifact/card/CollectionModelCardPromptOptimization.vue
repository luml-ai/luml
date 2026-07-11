<template>
  <div class="flow-wrapper">
    <VueFlow :default-viewport="{ zoom: 0.8 }">
      <template #node-custom="props">
        <custom-node :id="props.id" :data="props.data" />
      </template>
      <template #edge-custom="edgeProps">
        <custom-edge v-bind="edgeProps" />
      </template>
      <Background pattern-color="var(--dots-color)" />
    </VueFlow>
  </div>
</template>

<script setup lang="ts">
import type { PromptOptimizationModelMetadataPayload } from '@/lib/data-processing/interfaces'
import { computed, watch } from 'vue'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { useVueFlow, VueFlow } from '@vue-flow/core'
import { Background } from '@vue-flow/background'
import CustomNode from '@/components/express-tasks/prompt-fusion/step-main/nodes/CustomNode.vue'
import CustomEdge from '@/components/ui/vue-flow/CustomEdge.vue'

type Props = {
  data: PromptOptimizationModelMetadataPayload
}

const props = defineProps<Props>()

const { addEdges, addNodes } = useVueFlow()

const vueFlowData = computed(() => promptFusionService.createFlowFromMetadata(props.data))

watch(
  vueFlowData,
  (data) => {
    addNodes(data.nodes)
    addEdges(data.edges)
  },
  { immediate: true },
)
</script>

<style scoped>
.flow-wrapper {
  width: 100%;
  height: calc(100vh - 300px);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  border-radius: 8px;
  box-shadow: var(--card-shadow);
}
</style>
