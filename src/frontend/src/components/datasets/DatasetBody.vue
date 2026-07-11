<template>
  <div>
    <div v-if="!datasetsStore.isInitialized">
      <Skeleton style="height: 73.5px; margin-bottom: 12px"></Skeleton>
      <Skeleton style="height: calc(100vh - 470px)"></Skeleton>
    </div>

    <DatasetContent v-else></DatasetContent>
  </div>
</template>

<script setup lang="ts">
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useDatasetsStore } from '@/stores/datasets'
import { Skeleton, useToast } from 'primevue'
import { onBeforeMount, watch } from 'vue'
import DatasetContent from './DatasetContent.vue'

const datasetsStore = useDatasetsStore()
const toast = useToast()

function setFirstSubset() {
  if (datasetsStore.subsets.length > 0) {
    datasetsStore.setSelectedSubset(datasetsStore.subsets[0].name)
  } else {
    datasetsStore.setSelectedSubset(null)
  }
}

function setFirstSplit() {
  if (datasetsStore.splitsList.length > 0) {
    datasetsStore.setSelectedSplit(datasetsStore.splitsList[0].name)
    datasetsStore.setCurrentPage(0)
  } else {
    datasetsStore.setSelectedSplit(null)
  }
}

async function init() {
  await datasetsStore.init()
  setFirstSubset()
}

onBeforeMount(async () => {
  if (datasetsStore.isInitialized) return
  try {
    await init()
  } catch (e) {
    const message = getErrorMessage(e, 'Failed to initialize datasets')
    toast.add(simpleErrorToast(message))
  }
})

watch(
  () => datasetsStore.subsets,
  () => {
    setFirstSubset()
  },
)

watch(
  () => datasetsStore.selectedSubset,
  () => {
    setFirstSplit()
  },
)
</script>

<style scoped></style>
