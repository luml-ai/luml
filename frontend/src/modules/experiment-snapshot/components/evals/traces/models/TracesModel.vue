<template>
  <div class="content">
    <div class="model-info">
      <div v-if="outputs">
        <header class="header">
          <div class="name">
            <CircuitBoard :size="16" color="var(--p-primary-color)" />
            <span>{{ name }}</span>
          </div>
          <Button v-if="spansExist" severity="secondary" variant="outlined" @click="showSpans">
            <ListTree :size="16" />
            Trace
          </Button>
        </header>
        <div class="items-list">
          <UiMultiTypeText
            v-for="item in outputs"
            :key="item.title"
            :title="item.title"
            :text="item.text"
          ></UiMultiTypeText>
        </div>
      </div>
      <div v-if="references" class="references">
        <header class="header">
          <div class="name">
            <FileText :size="16" color="var(--p-primary-color)" />
            <span>References</span>
          </div>
        </header>
        <div class="items-list">
          <UiMultiTypeText
            v-for="item in references"
            :key="item.title"
            :title="item.title"
            :text="item.text"
          ></UiMultiTypeText>
        </div>
      </div>
    </div>
    <div class="scores-block">
      <header class="header">
        <div class="name">
          <CircuitBoard :size="16" color="var(--p-primary-color)" />
          <span>Scores</span>
          <span style="color: var(--p-text-muted-color)">({{ scores.length }})</span>
        </div>
        <Button severity="secondary" variant="text" @click="toggleScores">
          <template #icon>
            <component :is="scoresBlockHeight ? Minimize2 : Maximize2" :size="16"></component>
          </template>
        </Button>
      </header>
      <div
        class="scores-block-content"
        :style="{
          height: scoresBlockHeight + 'px',
        }"
      >
        <div ref="scoresRef" class="scores-wrapper">
          <EvalsScoresSingle :scores="scores"></EvalsScoresSingle>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { CircuitBoard, FileText, Minimize2, Maximize2, ListTree } from 'lucide-vue-next'
import { Button, useToast } from 'primevue'
import { computed, onMounted, ref } from 'vue'
import { useEvalsStore } from '@/modules/experiment-snapshot/store/evals'
import { simpleErrorToast } from '@/modules/experiment-snapshot/lib/primevue/data/toasts'
import UiMultiTypeText from '../../../ui/UiMultiTypeText.vue'
import EvalsScoresSingle from '../../scores/single/EvalsScoresSingle.vue'

type Props = {
  id: string
  name: string
}

const props = defineProps<Props>()

const evalsStore = useEvalsStore()

const toast = useToast()

const scoresRef = ref<HTMLDivElement | null>()
const scoresBlockHeight = ref(0)
const spansExist = ref(false)

const modelData = computed(() =>
  evalsStore.currentEvalData?.find((item) => item.modelId === props.id),
)

const scores = computed(() => {
  if (!modelData.value) return []
  const result = Object.entries(modelData.value.scores).map(([name, value]) => ({
    name,
    value: +value,
  }))
  return result.filter((item) => !isNaN(item.value))
})

const outputs = computed(() => {
  const outputs = modelData.value?.outputs
  if (!outputs) return null
  return getFormattedItems(outputs)
})

const references = computed(() => {
  const references = modelData.value?.refs
  if (!references) return null
  return getFormattedItems(references)
})

function toggleScores() {
  const height = scoresRef.value?.clientHeight || 0
  if (scoresBlockHeight.value === 0) {
    scoresBlockHeight.value = height
  } else {
    scoresBlockHeight.value = 0
  }
}

function getFormattedItems(object: object) {
  return Object.entries(object).map((item) => ({ title: item[0], text: item[1] }))
}

async function showSpans() {
  try {
    if (!evalsStore.selectedEval) throw new Error('No dataset or eval selected')
    const { datasetId, evalId } = evalsStore.selectedEval
    const trace = await evalsStore.getEvalSpansTree(props.id, datasetId, evalId)
    evalsStore.setSelectedTrace(trace)
  } catch {
    toast.add(simpleErrorToast('Failed to load spans'))
  }
}

onMounted(async () => {
  if (!evalsStore.selectedEval) {
    spansExist.value = false
  } else {
    const { datasetId, evalId } = evalsStore.selectedEval
    const traceId = await evalsStore.getTraceId(props.id, datasetId, evalId)
    spansExist.value = !!traceId
  }
})
</script>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  height: 100%;
  flex: 1 1 auto;
  min-width: 434px;
}
.content:not(:last-child) {
  border-right: 1px solid var(--p-divider-border-color);
}
.model-info {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 0 20px 20px;
  overflow-y: auto;
  flex: 1 1 auto;
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
  min-height: 33px;
}
.name {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 14px;
  font-weight: 500;
}
.scores-block {
  border-top: 1px solid var(--p-divider-border-color);
  flex: 0 0 auto;
  padding: 0 20px;
}
.items-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.scores-block-content {
  max-height: 400px;
  transition: height 0.3s ease-in-out;
  overflow-y: auto;
}
.scores-wrapper {
  padding-bottom: 20px;
}
</style>
