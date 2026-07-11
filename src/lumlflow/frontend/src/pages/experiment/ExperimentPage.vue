<template>
  <template v-if="loading">
    <Skeleton height="49px" class="mb-2"></Skeleton>
    <Skeleton height="27px" class="mb-2"></Skeleton>
    <Skeleton class="h-[calc(100vh-200px)]" height="calc(100vh-200px)"></Skeleton>
  </template>
  <div v-else>
    <ExperimentBreadcrumbs
      v-if="groupsStore.detailedGroup"
      :experiment="groupsStore.detailedGroup"
    />
    <h1 v-if="groupsStore.detailedGroup" class="text-2xl font-medium pt-5 mb-7">
      {{ groupsStore.detailedGroup.name }}
    </h1>
    <ExperimentWrapper
      v-if="groupId && groupsStore.detailedGroup"
      :groups-ids="[groupId]"
      :dynamic-metrics="experimentsStore.dynamicMetrics"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { errorToast } from '@/toasts'
import { Skeleton, useToast } from 'primevue'
import { useGroupsStore } from '@/store/groups'
import { useExperimentsStore } from '@/store/experiments'
import ExperimentBreadcrumbs from '@/components/experiments/experiment/ExperimentBreadcrumbs.vue'
import ExperimentWrapper from '@/components/experiments/experiment/ExperimentWrapper.vue'

const toast = useToast()
const route = useRoute()
const groupsStore = useGroupsStore()
const experimentsStore = useExperimentsStore()

const loading = ref(true)

const groupId = computed(() => (route.params.groupId ? String(route.params.groupId) : null))

onBeforeMount(async () => {
  try {
    if (!groupId.value) throw new Error('Group ID is required')
    const group = await groupsStore.getGroupById(groupId.value)
    if (!group) throw new Error('Group not found')
    groupsStore.setDetailedGroup(group)
    await experimentsStore.fetchDynamicMetrics([groupId.value])
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
