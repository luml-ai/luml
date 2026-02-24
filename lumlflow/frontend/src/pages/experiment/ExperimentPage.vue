<template>
  <div>
    <ExperimentBreadcrumbs
      v-if="groupsStore.detailedGroup"
      :experiment="groupsStore.detailedGroup"
    />
    <h1 v-if="groupsStore.detailedGroup" class="text-2xl font-medium pt-5 mb-7">
      {{ groupsStore.detailedGroup.name }}
    </h1>
    <ExperimentWrapper v-if="groupId" :group-id="groupId" />
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount } from 'vue'
import { useRoute } from 'vue-router'
import { errorToast } from '@/toasts'
import { useToast } from 'primevue'
import { useGroupsStore } from '@/store/groups'
import ExperimentBreadcrumbs from '@/components/experiments/experiment/ExperimentBreadcrumbs.vue'
import ExperimentWrapper from '@/components/experiments/experiment/ExperimentWrapper.vue'

const toast = useToast()
const route = useRoute()
const groupsStore = useGroupsStore()

const groupId = computed(() => (route.params.groupId ? String(route.params.groupId) : null))

onBeforeMount(async () => {
  if (!groupId.value) return
  try {
    const group = await groupsStore.getGroupById(groupId.value)
    if (!group) throw new Error('Group not found')
    groupsStore.setDetailedGroup(group)
  } catch (error) {
    toast.add(errorToast(error))
  }
})
</script>

<style scoped></style>
