<template>
  <div v-if="!loading" class="list">
    <UiCardAdd
      title="Add new Satellite"
      text="Keep checkpoints and configs in one place."
      v-if="!satellitesStore.satellitesList.length"
      @add="satellitesStore.showCreator"
    ></UiCardAdd>
    <template v-else>
      <SatellitesCard
        v-for="card in satellitesStore.satellitesList"
        :key="card.id"
        :data="card"
      ></SatellitesCard>
    </template>
  </div>
  <SatellitesCreateModal
    :visible="satellitesStore.creatorVisible"
    @update:visible="(val) => (val ? satellitesStore.showCreator() : satellitesStore.hideCreator())"
    @create="onCreate"
  ></SatellitesCreateModal>
  <SatellitesApiKeyModal
    v-if="createdSatellite"
    :api-key="createdSatellite.api_key"
    :satellite-id="createdSatellite.satellite.id"
    :visible="!!createdSatellite"
    @update:visible="onApiKeyClose"
  ></SatellitesApiKeyModal>
</template>

<script setup lang="ts">
import type { CreateSatelliteResponse } from '@/lib/api/satellites/interfaces'
import { onBeforeMount, ref } from 'vue'
import { useSatellitesStore } from '@/stores/satellites'
import { useRoute } from 'vue-router'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import SatellitesCreateModal from '@/components/satellites/SatellitesCreateModal.vue'
import UiCardAdd from '@/components/ui/UiCardAdd.vue'
import SatellitesApiKeyModal from '@/components/satellites/SatellitesApiKeyModal.vue'
import SatellitesCard from '@/components/satellites/SatellitesCard.vue'

const route = useRoute()
const toast = useToast()
const satellitesStore = useSatellitesStore()

const createdSatellite = ref<CreateSatelliteResponse | null>(null)
const loading = ref(false)

function onCreate(event: CreateSatelliteResponse) {
  createdSatellite.value = event
  satellitesStore.hideCreator()
}

function onApiKeyClose() {
  createdSatellite.value = null
}

onBeforeMount(async () => {
  try {
    loading.value = true
    const organizationId = +route.params.organizationId
    const orbitId = +route.params.id
    if (!organizationId) {
      throw new Error('Current organization was not found')
    }
    if (!orbitId) {
      throw new Error('Current orbit was not found')
    }
    const list = await satellitesStore.loadSatellites(organizationId, orbitId)
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
})
</script>

<style scoped>
.list {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
</style>
