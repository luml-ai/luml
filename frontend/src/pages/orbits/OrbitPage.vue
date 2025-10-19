<template>
  <div>
    <UiPageLoader v-if="loading"></UiPageLoader>

    <Ui404 v-else-if="!orbitsStore.currentOrbitDetails"></Ui404>
    <div v-else class="orbit-page">
      <header class="header">
        <h2 class="title">
          {{ orbitsStore.currentOrbitDetails?.name }}
          <UiId :id="orbitsStore.currentOrbitDetails.id" variant="button"></UiId>
        </h2>
        <Button v-if="buttonInfo" class="button" @click="buttonInfo.action">
          <Plus :size="14" />
          <span>{{ buttonInfo.label }}</span>
        </Button>
      </header>
      <OrbitTabs></OrbitTabs>
      <div class="view">
        <RouterView></RouterView>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref, watch } from 'vue'
import { useToast, Button } from 'primevue'
import { useOrbitsStore } from '@/stores/orbits'
import { useRoute, useRouter } from 'vue-router'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import Ui404 from '@/components/ui/Ui404.vue'
import OrbitTabs from '@/components/orbits/tabs/OrbitTabs.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import { useOrganizationStore } from '@/stores/organization'
import { Plus } from 'lucide-vue-next'
import { useSatellitesStore } from '@/stores/satellites'
import { useCollectionsStore } from '@/stores/collections'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { useDeploymentsStore } from '@/stores/deployments'
import UiId from '@/components/ui/UiId.vue'

const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const satellitesStore = useSatellitesStore()
const secretsStore = useSecretsStore()
const collectionsStore = useCollectionsStore()
const deploymentsStore = useDeploymentsStore()
const route = useRoute()
const router = useRouter()
const toast = useToast()

const loading = ref(false)

async function loadOrbitDetails() {
  try {
    loading.value = true
    orbitsStore.setCurrentOrbitDetails(null)
    const details = await orbitsStore.getOrbitDetails(
      String(route.params.organizationId),
      String(route.params.id),
    )
    orbitsStore.setCurrentOrbitDetails(details)
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load orbit data'))
  } finally {
    loading.value = false
  }
}

const buttonInfo = computed(() => {
  if (route.name === 'orbit-registry') {
    return {
      label: 'Create collection',
      action: () => {
        collectionsStore.showCreator()
      },
    }
  } else if (route.name === 'orbit-satellites') {
    return {
      label: 'Create satellite',
      action: () => {
        satellitesStore.showCreator()
      },
    }
  } else if (route.name === 'orbit-secrets') {
    return {
      label: 'Create secrets',
      action: () => {
        secretsStore.showCreator()
      },
    }
  } else if (route.name === 'orbit-deployments') {
    return {
      label: 'Create deployment',
      action: () => {
        deploymentsStore.showCreator()
      },
    }
  } else {
    return null
  }
})

watch(
  () => organizationStore.currentOrganization?.id,
  async (id) => {
    if (!id || route.params.organizationId === id) return

    await router.push({ name: 'orbits', params: { organizationId: id } })
  },
)

onBeforeMount(async () => {
  loadOrbitDetails()
})
</script>

<style scoped>
.orbit-page {
  padding: 32px 0;
}

.view {
  padding-top: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 40px;
  margin-bottom: 20px;
}

.title {
  display: flex;
  align-items: center;
  gap: 12px;
}
</style>
