<template>
  <div class="wrapper">
    <presentation-area :initial-nodes="initialNodes" />
    <Transition>
      <sidebar v-if="activeNode" :data="activeNode.data" class="sidebar" @close="closeSidebar" />
    </Transition>
    <control-center />
    <navigation @go-back="$emit('goBack')" />
    <toolbar />
  </div>
  <ui-training
    v-model="isTrainingActive"
    :time="8"
    :is-cancel-available="true"
    @cancel="cancelTraining"
  />
  <prompt-fusion-predict />
</template>

<script setup lang="ts">
import type { PromptNode } from '../interfaces'
import { onBeforeMount, onBeforeUnmount, ref } from 'vue'
import { useVueFlow, type GraphNode } from '@vue-flow/core'
import { promptFusionService } from '@/lib/promt-fusion/PromptFusionService'
import { DataProcessingWorker } from '@/lib/data-processing/DataProcessingWorker'
import { useRouteLeaveConfirm } from '@/hooks/useRouteLeaveConfirm'
import { leavePageConfirmOptions } from '@/lib/primevue/data/confirm'
import PresentationArea from '@/components/express-tasks/prompt-fusion/step-main/PresentationArea.vue'
import Sidebar from '@/components/express-tasks/prompt-fusion/step-main/sidebar/index.vue'
import Navigation from '@/components/express-tasks/prompt-fusion/step-main/Navigation.vue'
import Toolbar from '@/components/express-tasks/prompt-fusion/step-main/Toolbar.vue'
import ControlCenter from '@/components/express-tasks/prompt-fusion/step-main/control-center/index.vue'
import UiTraining from '@/components/ui/UiTraining.vue'
import PromptFusionPredict from './predict/PromptFusionPredict.vue'

type Props = {
  initialNodes: PromptNode[]
}
type Emits = {
  goBack: []
}

defineProps<Props>()
defineEmits<Emits>()

const { onNodeClick, onPaneClick } = useVueFlow()

const { setGuard } = useRouteLeaveConfirm(leavePageConfirmOptions(() => {}))

const activeNode = ref<GraphNode | null>(null)
const isTrainingActive = ref(false)

function closeSidebar() {
  activeNode.value = null
}
async function cancelTraining() {
  DataProcessingWorker.interrupt()
  promptFusionService.endTraining()
}
function onChangeTrainingState(value: boolean) {
  isTrainingActive.value = value
}

onNodeClick(({ node }) => {
  activeNode.value = node
})
onPaneClick(() => {
  activeNode.value = null
})

onBeforeMount(() => {
  promptFusionService.on('CHANGE_TRAINING_STATE', onChangeTrainingState)
  setGuard(true)
})
onBeforeUnmount(() => {
  promptFusionService.off('CHANGE_TRAINING_STATE', onChangeTrainingState)
})
</script>

<style scoped>
.wrapper {
  position: relative;
}
@media (min-width: 768px) {
  .wrapper {
    margin: 0 -100px;
    height: calc(100vh - 124px);
  }
}

.sidebar {
  position: absolute;
  width: 100%;
  top: 70px;
  bottom: -15px;
  right: 10px;
  z-index: 10;
}

.v-enter-active,
.v-leave-active {
  transition: transform 0.5s ease;
}

.v-enter-from,
.v-leave-to {
  transform: translateX(100%);
}
</style>
