<template>
  <div class="page-header">
    <div class="page-header__left">
      <Satellite :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Satellites</h1>
    </div>

    <d-button
      v-if="orbitsStore.currentOrbitDetails && authStore.isAuth"
      label="Add satellite"
      @click="satellitesStore.showCreator()"
    >
      <template #icon>
        <Plus :size="14" />
      </template>
    </d-button>
  </div>

  <UiPageLoader v-if="orbitsStore.isLoadingOrbitDetails" />

  <OrbitEmptyState v-else-if="!orbitsStore.currentOrbitId" :cards="satellitesCards" />

  <template v-else>
    <div v-if="!loading" class="list">
      <UiCardAdd
        v-if="!satellitesStore.satellitesList.length"
        title="Add new Satellite"
        text="Connect external compute resources as satellites."
        @add="satellitesStore.showCreator()"
      />
      <template v-else>
        <SatellitesCard
          v-for="card in satellitesStore.satellitesList"
          :key="card.id"
          :data="card"
        />
      </template>
    </div>

    <SatellitesCreateModal
      :visible="satellitesStore.creatorVisible"
      @update:visible="
        (val) => (val ? satellitesStore.showCreator() : satellitesStore.hideCreator())
      "
      @create="onCreate"
    />
    <SatellitesApiKeyModal
      v-if="createdSatellite"
      :api-key="createdSatellite.api_key"
      :satellite-id="createdSatellite.satellite.id"
      :visible="!!createdSatellite"
      @update:visible="onApiKeyClose"
    />
  </template>
</template>

<script setup lang="ts">
import type { CreateSatelliteResponse } from '@/lib/api/satellites/interfaces'
import { onBeforeMount, ref, watch } from 'vue'
import { useSatellitesStore } from '@/stores/satellites'
import { useOrbitsStore } from '@/stores/orbits'
import { useAuthStore } from '@/stores/auth'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import SatellitesCreateModal from '@/components/satellites/SatellitesCreateModal.vue'
import UiCardAdd from '@/components/ui/UiCardAdd.vue'
import SatellitesApiKeyModal from '@/components/satellites/SatellitesApiKeyModal.vue'
import SatellitesCard from '@/components/satellites/SatellitesCard.vue'
import OrbitEmptyState from '@/components/orbits/OrbitEmptyState.vue'
import { Satellite, Plus } from 'lucide-vue-next'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'

const authStore = useAuthStore()
const toast = useToast()
const satellitesStore = useSatellitesStore()
const orbitsStore = useOrbitsStore()

const createdSatellite = ref<CreateSatelliteResponse | null>(null)
const loading = ref(false)

const satellitesCards = [
  {
    title: 'Satellites',
    description:
      'A Satellite is an external compute node that connects to LUML via a pairing key and becomes the execution environment for an Orbit.',
  },
  {
    title: 'How it works',
    description:
      'The platform queues tasks, and the Satellite pulls and executes them within your own infrastructure, remaining fully under your control.',
  },
]

async function loadSatellitesList() {
  if (!orbitsStore.currentOrbitDetails) return
  try {
    loading.value = true
    const list = await satellitesStore.loadSatellites(
      orbitsStore.currentOrbitDetails.organization_id,
      orbitsStore.currentOrbitDetails.id,
    )
    satellitesStore.setList(list)
  } catch (e: any) {
    toast.add(
      simpleErrorToast(
        e?.response?.detail?.message || e?.message || 'Failed to load satellites list',
      ),
    )
  } finally {
    loading.value = false
  }
}

function onCreate(event: CreateSatelliteResponse) {
  createdSatellite.value = event
  satellitesStore.hideCreator()
}

function onApiKeyClose() {
  createdSatellite.value = null
}

watch(
  () => orbitsStore.currentOrbitDetails?.id,
  async (newId) => {
    if (!newId) return
    await loadSatellitesList()
  },
  { immediate: true },
)

onBeforeMount(async () => {
  await loadSatellitesList()
})
</script>

<style scoped>
.list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

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
</style>
