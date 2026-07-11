<template>
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
    v-if="artifactsStore.experimentSnapshotProvider && artifactsStore.currentArtifact"
    :provider="artifactsStore.experimentSnapshotProvider"
    :models-ids="[String(artifactsStore.currentArtifact.id)]"
    :models-info="artifactsInfo"
    :theme="themeStore.getCurrentTheme"
  ></ExperimentSnapshot>
</template>

<script setup lang="ts">
import type { ModelInfo } from '@luml/experiments'
import { ExperimentSnapshot } from '@luml/experiments'
import { computed, onBeforeMount, ref } from 'vue'
import { useArtifactsStore } from '@/stores/artifacts'
import { Skeleton } from 'primevue'
import { useExperimentSnapshotsDatabaseProvider } from '@/hooks/useExperimentSnapshotsDatabaseProvider'
import { getArtifactColorByIndex } from '@/helpers/helpers'
import { useThemeStore } from '@/stores/theme'

const artifactsStore = useArtifactsStore()
const { init } = useExperimentSnapshotsDatabaseProvider()
const themeStore = useThemeStore()

const loading = ref(true)

const artifactsInfo = computed(() => {
  const data: Record<string, ModelInfo> = {}
  if (artifactsStore.currentArtifact) {
    data[artifactsStore.currentArtifact.id] = {
      name: artifactsStore.currentArtifact.name,
      color: getArtifactColorByIndex(0),
    }
  }
  return data
})

onBeforeMount(async () => {
  if (artifactsStore.experimentSnapshotProvider) {
    loading.value = false
    return
  }
  try {
    loading.value = true
    if (!artifactsStore.currentArtifact) throw new Error('Current artifact does not exist')
    await init([artifactsStore.currentArtifact])
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
