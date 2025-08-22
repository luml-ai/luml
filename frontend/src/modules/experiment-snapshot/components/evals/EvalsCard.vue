<template>
  <UiCard title="Evals">
    <EvalsScoresSingle
      v-if="averageScores.length === 1"
      :scores="averageScores[0].scores"
    ></EvalsScoresSingle>
    <EvalsScoresMultiple
      v-else
      :models-scores="averageScores"
      :models-info="modelsInfo"
    ></EvalsScoresMultiple>
    <EvalsTable
      :columns-tree="columnsTree"
      :data="tableData"
      :models-info="modelsInfo"
    ></EvalsTable>
  </UiCard>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { EvalsInfo, ModelsInfo } from '../../interfaces/interfaces'
import UiCard from '../ui/UiCard.vue'
import EvalsTable, { type EvalsTableColumn } from './EvalsTable.vue'
import EvalsScoresSingle from './scores/single/EvalsScoresSingle.vue'
import EvalsScoresMultiple from './scores/multiple/EvalsScoresMultiple.vue'

type Props = {
  data: EvalsInfo[]
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const tableData = computed(() => {
  return props.data.map((item) => {
    const entries = Object.entries(item)
    return entries.reduce((acc: Record<string, any>, entry) => {
      if (typeof entry[1] !== 'object') {
        acc[entry[0]] = entry[1]
      } else {
        Object.entries(entry[1]).map((child) => {
          acc[child[0]] = child[1]
        })
      }
      return acc
    }, {})
  })
})

const columnsTree = computed(() => {
  return props.data.reduce((acc: EvalsTableColumn[], item) => {
    const entries = Object.entries(item)
    entries.forEach((entry) => {
      const title = entry[0]
      const children = typeof entry[1] === 'object' ? Object.keys(entry[1]) : undefined
      const existedColumn = acc.find((column) => column.title === title)
      if (existedColumn) {
        existedColumn.children = sumUniqueChildren(existedColumn.children, children)
      } else {
        acc.push({ title, children })
      }
    })
    return acc
  }, [])
})

const averageScores = computed(() => {
  return getAverageScore(props.data)
})

function getAverageScore(evals: EvalsInfo[]) {
  const sums: Record<string, Record<string, number>> = {}
  const counts: Record<string, Record<string, number>> = {}

  for (const item of evals) {
    const modelId = item.modelId
    if (!modelId || typeof item.scores !== 'object') continue

    if (!sums[modelId]) {
      sums[modelId] = {}
      counts[modelId] = {}
    }

    for (const key in item.scores) {
      const val = item.scores[key]
      if (typeof val === 'number') {
        sums[modelId][key] = (sums[modelId][key] ?? 0) + val
        counts[modelId][key] = (counts[modelId][key] ?? 0) + 1
      }
    }
  }

  return Object.keys(sums).map((modelId) => ({
    modelId,
    scores: Object.keys(sums[modelId]).map((scoreName) => ({
      name: scoreName,
      value: sums[modelId][scoreName] / counts[modelId][scoreName],
    })),
  }))
}

function sumUniqueChildren(accumulated?: string[], newChildren?: string[]) {
  if (!newChildren) return accumulated
  if (!accumulated) return newChildren
  const childrenSet = new Set([...accumulated, ...newChildren])
  return Array.from(childrenSet)
}
</script>

<style scoped></style>
