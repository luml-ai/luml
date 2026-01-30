<template>
  <div class="charts">
    <EvalsScoresMultipleItem
      v-for="data in chartsData"
      :key="data[0]?.scoreName"
      :data="data"
    ></EvalsScoresMultipleItem>
  </div>
</template>

<script setup lang="ts">
import type { ModelScores, ModelsInfo } from '@/interfaces/interfaces'
import { computed } from 'vue'
import EvalsScoresMultipleItem from './EvalsScoresMultipleItem.vue'

type Props = {
  modelsScores: ModelScores[]
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const uniqueScores = computed(() => {
  const scoresSet = props.modelsScores.reduce((acc, modelScores) => {
    modelScores.scores.map((score) => acc.add(score.name))
    return acc
  }, new Set<string>())
  return Array.from(scoresSet)
})

const chartsData = computed(() => {
  return uniqueScores.value.map((scoreName) => getScoreChartInfo(scoreName))
})

function getScoreChartInfo(scoreName: string) {
  return props.modelsScores
    .map((item) => {
      const modelId = item.modelId
      const modelInfo = props.modelsInfo[modelId]
      const modelName = modelInfo?.name || 'Unknown model'
      const color = modelInfo?.color || 'var(--p-text-muted-color)'
      const value = item.scores.find((score) => score.name === scoreName)?.value
      return { modelName, color, value, scoreName }
    })
    .filter((item) => item.value !== undefined)
}
</script>

<style scoped>
.charts {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
  padding-bottom: 20px;
}
</style>
