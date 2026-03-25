<template>
  <div class="page-header">
    <div class="page-header__left">
      <Rocket :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Deployments</h1>
    </div>
    <template v-if="orbitsStore.currentOrbitDetails && authStore.isAuth">
      <d-button
        v-if="activeTab === 'deployments'"
        label="Create deployment"
        @click="deploymentsStore.showCreator()"
      >
        <template #icon>
          <Plus :size="14" />
        </template>
      </d-button>
      <d-button v-else label="Create secret" @click="secretsStore.showCreator()">
        <template #icon>
          <Plus :size="14" />
        </template>
      </d-button>
    </template>
  </div>

  <UiPageLoader v-if="orbitsStore.isLoadingOrbitDetails" />

  <OrbitEmptyState v-else-if="!orbitsStore.currentOrbitId" :cards="deploymentsCards" />

  <template v-else>
    <div class="tabs">
      <button
        class="tab"
        :class="{ active: activeTab === 'deployments' }"
        @click="switchTab('deployments')"
      >
        <Rocket :size="14" />
        <span>Deployments</span>
      </button>
      <button
        class="tab"
        :class="{ active: activeTab === 'secrets' }"
        @click="switchTab('secrets')"
      >
        <Lock :size="14" />
        <span>Secrets</span>
      </button>
    </div>

    <template v-if="activeTab === 'deployments'">
      <div v-if="!deploymentsLoading">
        <template v-if="deploymentsStore.deployments.length">
          <div class="message">
            <BellRing :size="14" /> In order to use the inference URL, please authorize with your
            API key
          </div>
          <DeploymentsTable :data="deploymentsStore.deployments" />
        </template>
        <div v-else class="list">
          <UiCardAdd
            title="Add new Deployment"
            text="Instantly deploy models in a single click."
            @add="deploymentsStore.showCreator()"
          />
        </div>
      </div>
    </template>

    <template v-if="activeTab === 'secrets'">
      <div v-if="!secretsLoading && orbitsStore.currentOrbitDetails">
        <SecretsList
          :organization-id="orbitsStore.currentOrbitDetails!.organization_id"
          :edit-available="true"
          :copy-available="true"
        />
      </div>
    </template>
  </template>

  <DeploymentsCreateModal
    v-if="deploymentsStore.creatorVisible"
    :visible="deploymentsStore.creatorVisible"
    @update:visible="
      (val) => (val ? deploymentsStore.showCreator() : deploymentsStore.hideCreator())
    "
  />
  <SecretCreator
    :organization-id="orbitsStore.currentOrbitDetails?.organization_id"
    :orbit-id="orbitsStore.currentOrbitId ?? undefined"
    v-model:visible="secretsStore.creatorVisible"
    @update:visible="(val) => (val ? secretsStore.showCreator() : secretsStore.hideCreator())"
  />
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeploymentsStore } from '@/stores/deployments'
import { useOrbitsStore } from '@/stores/orbits'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { useAuthStore } from '@/stores/auth'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { BellRing, Rocket, Lock, Plus } from 'lucide-vue-next'
import UiCardAdd from '@/components/ui/UiCardAdd.vue'
import DeploymentsCreateModal from '@/components/deployments/create/DeploymentsCreateModal.vue'
import DeploymentsTable from '@/components/deployments/table/DeploymentsTable.vue'
import OrbitEmptyState from '@/components/orbits/OrbitEmptyState.vue'
import SecretsList from '@/components/orbit-secrets/SecretsList.vue'
import SecretCreator from '@/components/orbit-secrets/SecretCreator.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const deploymentsStore = useDeploymentsStore()
const orbitsStore = useOrbitsStore()
const secretsStore = useSecretsStore()
const toast = useToast()

const deploymentsLoading = ref(false)
const secretsLoading = ref(false)

const activeTab = computed(() => {
  return route.name === 'orbit-secrets' ? 'secrets' : 'deployments'
})

function switchTab(tab: 'deployments' | 'secrets') {
  const targetRoute = tab === 'secrets' ? 'orbit-secrets' : 'orbit-deployments'
  router.push({
    name: targetRoute,
    params: route.params,
    query: route.query,
  })
}

async function loadDeployments() {
  if (!orbitsStore.currentOrbitDetails) return
  try {
    deploymentsLoading.value = true
    const deployments = await deploymentsStore.getDeployments(
      orbitsStore.currentOrbitDetails.organization_id,
      orbitsStore.currentOrbitDetails.id,
    )
    deploymentsStore.setDeployments(deployments)
  } catch (e: any) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load deployments list')))
  } finally {
    deploymentsLoading.value = false
  }
}

async function loadSecrets() {
  if (!orbitsStore.currentOrbitDetails) return
  try {
    secretsLoading.value = true
    await secretsStore.loadSecrets(
      orbitsStore.currentOrbitDetails.organization_id,
      orbitsStore.currentOrbitDetails.id,
    )
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load secrets'))
  } finally {
    secretsLoading.value = false
  }
}

async function loadAll() {
  if (!orbitsStore.currentOrbitDetails) return
  await Promise.all([loadDeployments(), loadSecrets()])
}

const deploymentsCards = [
  {
    title: 'Deployments',
    description:
      'A Deployment transforms a model from the Registry into a live endpoint by linking it to a Satellite. You can create, update, stop, or delete it without changing the model itself.',
  },
  {
    title: 'Secrets',
    description:
      'Secrets is a secure store for sensitive data scoped to an Orbit. When a key is rotated, the update automatically propagates to all linked deployments.',
  },
]

watch(
  () => orbitsStore.currentOrbitDetails?.id,
  async (newId) => {
    if (!newId) return
    await loadAll()
  },
  { immediate: true },
)

onUnmounted(() => {
  deploymentsStore.reset()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 25px;
  padding-top: 37px;
}

.page-header__left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.page-header__icon {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
  aspect-ratio: 1/1;
  color: var(--p-primary-color);
}

.page-header__title {
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
}

.tabs {
  display: flex;
  gap: 0;
  border-bottom: 1px solid var(--p-divider-border-color);
  margin-bottom: 25px;
}

.tab {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 16px;
  color: var(--tabs-tab-color);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition:
    color 0.2s,
    border-color 0.2s;
  margin-bottom: -1px;
}

.tab.active {
  color: var(--p-primary-color);
  border-bottom-color: var(--p-primary-color);
}

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
