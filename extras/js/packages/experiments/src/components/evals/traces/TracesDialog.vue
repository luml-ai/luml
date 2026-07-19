<template>
  <Dialog v-model:visible="visible" :draggable="false" :pt="dialogPt" position="right">
    <div v-if="showLoader" class="inputs-loader">
      <Skeleton height="calc(100% - 20px)" />
    </div>
    <TracesInputs v-else :models-info="modelsInfo"></TracesInputs>
    <div class="main-content">
      <EvalsTabs
        v-if="evalsStore.evalsIdsList.length > 1"
        :ids="evalsStore.evalsIdsList"
        :current-id="evalsStore.currentEvalId"
        @update:current-id="onCurrentEvalIdUpdate"
      ></EvalsTabs>
      <div v-if="showLoader" class="models-loader">
        <Skeleton height="calc(100% - 20px)" />
      </div>
      <TracesModels v-else :models-info="modelsInfo" class="models"></TracesModels>
    </div>
  </Dialog>
</template>

<script setup lang="ts">
import type { DialogPassThroughOptions } from 'primevue'
import type { ModelsInfo } from '@/interfaces/interfaces'
import { Dialog, Skeleton, useToast } from 'primevue'
import TracesInputs from './inputs/TracesInputs.vue'
import TracesModels from './models/TracesModels.vue'
import EvalsTabs from './EvalsTabs.vue'
import { useEvalsStore } from '@/store/evals'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useMinLoading } from '@/hooks/useMinLoading'
import { computed } from 'vue'

type Props = {
  modelsInfo: ModelsInfo
}

defineProps<Props>()

const toast = useToast()

const dialogPt: DialogPassThroughOptions = {
  mask: {
    style: 'align-items: flex-start; padding: 64px 0 56px;',
  },
  root: {
    style: 'width: calc(100vw - 32px); height: 100%; max-height: none;',
  },
  header: {
    style: 'padding: 16px 20px; justify-content: flex-end;',
  },
  content: {
    style: 'display: flex; padding: 0; overflow: hidden;',
  },
  pcCloseButton: {},
}

const visible = defineModel<boolean>('visible')

const evalsStore = useEvalsStore()
const showLoader = useMinLoading(computed(() => evalsStore.currentEvalDataLoading))

async function onCurrentEvalIdUpdate(evalId: string) {
  try {
    evalsStore.setCurrentEvalDataLoading(true)
    const artifactId = evalsStore.currentEvalData?.[0]?.modelId
    if (!artifactId) return
    const evalData = await evalsStore.getProvider.getEvalById(artifactId, evalId)
    evalsStore.setCurrentEvalData([evalData])
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  } finally {
    evalsStore.setCurrentEvalDataLoading(false)
  }
}
</script>

<style scoped>
.main-content {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow: hidden;
}

.models {
  overflow-x: auto;
  flex: 1 1 auto;
}

.inputs-loader {
  width: 380px;
  border-right: 1px solid var(--p-divider-border-color);
  flex: 0 0 auto;
  overflow: hidden;
  padding: 0 20px;
}

.models-loader {
  padding: 0 20px;
  flex: 1 1 auto;
}
</style>
