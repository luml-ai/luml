<template>
  <div>
    <ComparisonHeader></ComparisonHeader>
    <ComparisonModelsList
      :models-ids="artifactIdsList"
      :models-list="artifactsList"
      :models-info="artifactsInfo"
    ></ComparisonModelsList>
    <div v-if="loading">
      <Skeleton style="height: 210px; margin-bottom: 20px"></Skeleton>
      <div
        style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px"
      >
        <Skeleton style="height: 300px; width: 100%"></Skeleton>
        <Skeleton style="height: 300px; width: 100%"></Skeleton>
      </div>
      <Skeleton style="height: 210px; margin-bottom: 20px"></Skeleton>
    </div>
    <ExperimentSnapshot
      v-else-if="artifactsStore.experimentSnapshotProvider"
      :provider="artifactsStore.experimentSnapshotProvider"
      :models-ids="artifactIdsList"
      :models-info="artifactsInfo"
      :theme="themeStore.getCurrentTheme"
    ></ExperimentSnapshot>
  </div>
</template>

<script setup lang="ts">
import type { ModelsInfo } from '@luml/experiments'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { ComparisonHeader, ComparisonModelsList, ExperimentSnapshot } from '@luml/experiments'
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useArtifactsStore } from '@/stores/artifacts'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'
import { Skeleton } from 'primevue'
import { getArtifactColorByIndex } from '@/helpers/helpers'
import { useThemeStore } from '@/stores/theme'

const route = useRoute()
const themeStore = useThemeStore()
const artifactsStore = useArtifactsStore()
const { init } = useExperimentSnapshotsDatabaseProvider()

const loading = ref(false)

const artifactIdsList = computed(() => {
  if (!route.query.artifacts) return []
  if (Array.isArray(route.query.artifacts)) {
    return route.query.artifacts.filter((artifact) => artifact !== null).map(String)
  }
  return [String(route.query.artifacts)]
})

const artifactsList = ref<Artifact[]>([])

const artifactsInfo = computed(() => {
  return artifactsList.value.reduce((acc: ModelsInfo, artifact, index) => {
    const name = artifact.name
    const color = getArtifactColorByIndex(index)
    acc[artifact.id] = { name, color }
    return acc
  }, {})
})

async function onArtifactIdsChange(newArtifactIds: string[]) {
  try {
    loading.value = true
    artifactsStore.resetExperimentSnapshotProvider()
    artifactsList.value = []
    const promises = await Promise.allSettled(
      newArtifactIds.map((artifactId) => artifactsStore.getArtifact(artifactId)),
    )
    const artifacts = promises
      .map((promise) => (promise.status === 'fulfilled' ? promise.value : null))
      .filter((artifact) => !!artifact)
    artifactsList.value = artifacts
    await init(artifactsList.value)
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
}

onUnmounted(() => {
  artifactsStore.resetExperimentSnapshotProvider()
})

watch(artifactIdsList, onArtifactIdsChange, { immediate: true, deep: true })
</script>

<style scoped>
.loading-block {
  min-height: 300px;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
