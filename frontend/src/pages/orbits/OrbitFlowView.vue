<template>
  <div class="page-header">
    <div class="page-header__left">
      <ChartSpline :size="20" class="page-header__icon" />
      <h1 class="page-header__title">Flow</h1>
    </div>

    <d-button label="Add flow" data-testid="add-flow" @click="addDialogVisible = true">
      <template #icon>
        <Plus :size="14" />
      </template>
    </d-button>
  </div>

  <div v-if="loading" class="list">
    <Skeleton v-for="i in 3" :key="i" style="height: 149px" />
  </div>

  <div v-else class="list">
    <UiCardAdd
      v-if="!localFlowsStore.localFlows.length && !flowsStore.flowsList.length"
      title="Add a flow"
      text="Open a Flow on this computer or on a remote machine."
      @add="addDialogVisible = true"
    />
    <template v-else>
      <LocalFlowCard
        v-for="flow in localFlowsStore.localFlows"
        :key="localFlowKey(flow)"
        :flow="flow"
        :reachable="reachability[localFlowKey(flow)] ?? null"
        @remove="localFlowsStore.removeLocalFlow(flow)"
      />
      <RelayedFlowCard
        v-for="flow in flowsStore.flowsList"
        :key="flow.id"
        :flow="flow"
        :organization-id="organizationId"
        :orbit-id="orbitId"
      />
    </template>
  </div>

  <FlowAddDialog
    v-model:visible="addDialogVisible"
    :organization-id="organizationId"
    :orbit-has-relay="!!orbitsStore.currentOrbitDetails?.relay_id"
    @added="(flow) => (reachability[localFlowKey(flow)] = true)"
  />
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { Skeleton, useToast } from 'primevue'
import { ChartSpline, Plus } from 'lucide-vue-next'
import { useFlowsStore } from '@/stores/flows'
import { isLocalFlowReachable, localFlowKey, useLocalFlowsStore } from '@/stores/local-flows'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import UiCardAdd from '@/components/ui/UiCardAdd.vue'
import FlowAddDialog from '@/components/flow/FlowAddDialog.vue'
import LocalFlowCard from '@/components/flow/LocalFlowCard.vue'
import RelayedFlowCard from '@/components/flow/RelayedFlowCard.vue'

const REFRESH_INTERVAL_MS = 10_000

const route = useRoute()
const toast = useToast()
const flowsStore = useFlowsStore()
const localFlowsStore = useLocalFlowsStore()
const orbitsStore = useOrbitsStore()

const organizationId = computed(() => route.params.organizationId as string)
const orbitId = computed(() => route.params.id as string)

const loading = ref(false)
const addDialogVisible = ref(false)
const reachability = ref<Record<string, boolean>>({})

async function checkLocalFlows() {
  await Promise.all(
    localFlowsStore.localFlows.map(async (flow) => {
      reachability.value[localFlowKey(flow)] = await isLocalFlowReachable(flow)
    }),
  )
}

async function loadRelayedFlows(reportErrors: boolean) {
  try {
    await flowsStore.loadFlows(organizationId.value, orbitId.value)
  } catch (e: unknown) {
    if (reportErrors) toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load flows')))
  }
}

async function refresh() {
  await Promise.all([loadRelayedFlows(false), checkLocalFlows()])
}

watch(
  orbitId,
  async (newId) => {
    if (!newId) return
    flowsStore.reset()
    loading.value = true
    await loadRelayedFlows(true)
    loading.value = false
    await checkLocalFlows()
  },
  { immediate: true },
)

const refreshInterval = setInterval(refresh, REFRESH_INTERVAL_MS)

onUnmounted(() => {
  clearInterval(refreshInterval)
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
  color: var(--p-primary-color);
}

.page-header__title {
  font-weight: 500;
  line-height: 30px;
  letter-spacing: -0.48px;
}
</style>
