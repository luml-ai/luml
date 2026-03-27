<template>
  <div class="setup-page">
    <UiPageLoader v-if="isLoading" />

    <template v-else>
      <div class="page-header">
        <div class="page-header__left">
          <component :is="currentTab.icon" :size="20" class="page-header__icon" />
          <h1 class="page-header__title">{{ currentTab.title }}</h1>
        </div>
      </div>

      <div class="grid">
        <div class="card card--action">
          <template v-if="!authStore.isAuth">
            <div class="content">
              <div class="title">Get Started</div>
              <p class="text">Log in or create an account to start using this feature.</p>
            </div>
            <div class="actions">
              <d-button
                label="Log in"
                severity="secondary"
                @click="$router.push({ name: 'sign-in', query: { redirect: $route.fullPath } })"
              />
              <d-button
                label="Sign up"
                @click="$router.push({ name: 'sign-up', query: { redirect: $route.fullPath } })"
              />
            </div>
          </template>

          <template v-else>
            <div class="content">
              <div class="title">Create an Orbit</div>
              <p class="text">
                Create your first orbit to start organizing models, deployments and satellites.
              </p>
            </div>
            <div class="actions">
              <d-button label="Create orbit" @click="isCreateOrbitMode = true" />
            </div>
          </template>
        </div>

        <div v-for="card in currentTab.cards" :key="card.title" class="card">
          <div class="content">
            <div class="title">{{ card.title }}</div>
            <p class="text">{{ card.description }}</p>
          </div>
        </div>
      </div>

      <OrbitCreator
        v-if="organizationStore.currentOrganization"
        v-model:visible="isCreateOrbitMode"
        :organization-id="organizationStore.currentOrganization.id"
        @created="onOrbitCreated"
      />
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Folders, Rocket, Satellite } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useOrganizationStore } from '@/stores/organization'
import { useOrbitsStore } from '@/stores/orbits'
import OrbitCreator from '@/components/orbits/creator/OrbitCreator.vue'
import UiPageLoader from '@/components/ui/UiPageLoader.vue'
import type { Orbit } from '@/lib/api/api.interfaces'
import { TAB_TO_ROUTE } from '@/constants/orbit-navigation'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()

const isCreateOrbitMode = ref(false)
const isLoading = ref(true)

onMounted(() => {
  isLoading.value = false
})

watch(
  () => organizationStore.currentOrganization?.id,
  async (orgId) => {
    if (!orgId || !authStore.isAuth) return

    isLoading.value = true

    if (!orbitsStore.orbitsList.length) {
      try {
        await orbitsStore.loadOrbitsList(orgId)
      } catch {
        isLoading.value = false
        return
      }
    }

    const firstOrbit = orbitsStore.orbitsList[0]
    if (!firstOrbit) {
      isLoading.value = false
      return
    }

    const tab = (route.query.tab as string) ?? 'registry'
    const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry'

    router.replace({
      name: targetRoute,
      params: { organizationId: orgId, id: firstOrbit.id },
    })
  },
)

const TABS: Record<
  string,
  { title: string; icon: any; cards: { title: string; description: string }[] }
> = {
  registry: {
    title: 'Registry',
    icon: Folders,
    cards: [
      {
        title: 'Registry',
        description:
          'Registry is a centralized hub for organizing and tracking ML models, experiments, and datasets — managing their versions and metadata throughout the entire lifecycle.',
      },
      {
        title: 'Overview',
        description:
          'Overview is a technical passport for any registry item — models, experiments, or datasets — containing metadata: name, date, size, content manifest, and tags for search and organization across collections.',
      },
    ],
  },
  deployments: {
    title: 'Deployments',
    icon: Rocket,
    cards: [
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
    ],
  },
  satellites: {
    title: 'Satellites',
    icon: Satellite,
    cards: [
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
    ],
  },
}

const currentTab = computed(() => {
  const tab = route.query.tab as string
  return TABS[tab] ?? TABS.registry
})

function onOrbitCreated(orbit: Orbit) {
  const tab = (route.query.tab as string) ?? 'registry'
  const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry'

  router.push({
    name: targetRoute,
    params: {
      organizationId: organizationStore.currentOrganization!.id,
      id: orbit.id,
    },
  })
}

onMounted(() => {
  isLoading.value = false
})
watch(
  () => organizationStore.currentOrganization?.id,
  async (orgId) => {
    if (!orgId || !authStore.isAuth) return

    isLoading.value = true

    if (!orbitsStore.orbitsList.length) {
      try {
        await orbitsStore.loadOrbitsList(orgId)
      } catch {
        isLoading.value = false
        return
      }
    }

    const firstOrbit = orbitsStore.orbitsList[0]
    if (!firstOrbit) {
      isLoading.value = false
      return
    }

    const tab = (route.query.tab as string) ?? 'registry'
    const targetRoute = TAB_TO_ROUTE[tab] ?? 'orbit-registry'

    router.replace({
      name: targetRoute,
      params: { organizationId: orgId, id: firstOrbit.id },
    })
  },
)
</script>

<style scoped>
.setup-page {
  padding: 0 16px;
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

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}

.card {
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  border-radius: 8px;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.title {
  font-size: 20px;
  font-weight: 500;
  line-height: 24px;
  margin-bottom: 8px;
  color: var(--p-text-color);
}

.text {
  color: var(--p-text-muted-color);
  font-size: 14px;
  font-weight: 400;
  line-height: 20px;
}

.actions {
  display: flex;
  gap: 12px;
  margin-top: auto;
}

.actions .p-button {
  flex: 1;
}

.dialog-title {
  font-weight: 600;
  font-size: 20px;
  text-transform: uppercase;
}

.dialog-text {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 300px;
}

@media (max-width: 992px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 576px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
