<template>
  <div v-if="!loading">
    <template v-if="deploymentsStore.deployments.length">
      <div class="message">
        <BellRing :size="14" /> In order to use the inference URL, please authorize with your API
        key
      </div>
      <DeploymentsTable :data="deploymentsStore.deployments"></DeploymentsTable>
    </template>
    <div v-else class="list">
      <UiCardAdd
        title="Add new Deployment"
        text="Keep versions and configs organized."
        @add="onAddClick"
      ></UiCardAdd>
    </div>
  </div>
  <DeploymentsCreateModal
    v-if="deploymentsStore.creatorVisible"
    :visible="deploymentsStore.creatorVisible"
    @update:visible="
      (val) => (val ? deploymentsStore.showCreator() : deploymentsStore.hideCreator())
    "
  ></DeploymentsCreateModal>
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted, ref } from 'vue'
import { useDeploymentsStore } from '@/stores/deployments'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { BellRing } from 'lucide-vue-next'
import UiCardAdd from '@/components/ui/UiCardAdd.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import DeploymentsTable from '@/components/deployments/table/DeploymentsTable.vue'

const deploymentsStore = useDeploymentsStore()
const route = useRoute()
const toast = useToast()

const loading = ref(true)

function onAddClick() {
  deploymentsStore.showCreator()
}

onBeforeMount(async () => {
  try {
    loading.value = true
    const organizationId = route.params.organizationId
    const orbitId = route.params.id
    if (!organizationId) {
      throw new Error('Current organization was not found')
    }
    if (!orbitId) {
      throw new Error('Current orbit was not found')
    }
    const deployments = await deploymentsStore.getDeployments(
      String(route.params.organizationId),
      String(route.params.id),
    )
    deploymentsStore.setDeployments(deployments)
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load deployments list')))
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  deploymentsStore.reset()
})
</script>

<style scoped>
.list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
}

.message {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
  padding: 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--p-tag-primary-color);
  background-color: var(--p-tag-primary-background);
  margin-bottom: 20px;
}
</style>
