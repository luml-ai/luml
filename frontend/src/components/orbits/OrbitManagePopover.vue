<template>
  <div class="orbit-popover-wrapper">
    <d-button variant="text" class="menu-link" @click="toggle">
      <Orbit :size="14" class="icon" />
      <span class="label">{{ orbitsStore.currentOrbit?.name ?? 'Orbit' }}</span>
      <ChevronDown :size="20" class="icon" />
    </d-button>
    <Popover
      ref="popover"
      appendTo="self"
      :dismissable="false"
      class="popover-without-arrow"
      style="width: 330px"
    >
      <div class="popover-content">
        <header v-if="orbitsStore.currentOrbit" class="header">
          <div class="header-content">
            <div class="name">{{ orbitsStore.currentOrbit.name }}</div>
            <div class="meta-row">
              <div class="collections-count">
                {{ orbitsStore.currentOrbitDetails?.total_collections ?? 0 }} collections
              </div>
              <div v-if="orbitsStore.currentOrbit.id" class="id-row">
                <UiId :id="orbitsStore.currentOrbit.id" class="id-value" />
              </div>
            </div>
          </div>
        </header>
        <div v-if="orbitsStore.orbitsList.length" class="popover-label">Switch to Orbit</div>
        <template v-if="orbitsStore.orbitsList.length">
          <div
            v-for="orbit in orbitsStore.orbitsList"
            :key="orbit.id"
            class="orbit-item"
            :class="{ active: orbit.id === orbitsStore.currentOrbit?.id }"
          >
            <button class="menu-item" @click="onOrbitClick(orbit.id)">
              {{ orbit.name }}
            </button>
            <d-button
              v-if="
                orbit.id === orbitsStore.currentOrbit?.id &&
                orbitsStore.currentOrbitDetails?.permissions?.orbit?.includes(PermissionEnum.update)
              "
              variant="text"
              severity="secondary"
              size="small"
              @click.stop="onSettingsClick"
            >
              <template #icon>
                <Bolt :size="14" />
              </template>
            </d-button>
          </div>
        </template>
        <div v-else class="empty">
          <p class="empty-text-header">Add new Orbit</p>
          <p class="empty-text">Start by creating an Orbit to organize your team's work</p>
        </div>
        <footer class="footer">
          <d-button
            v-if="createAvailable"
            severity="secondary"
            :disabled="isOrbitLimitReached"
            v-tooltip.top="isOrbitLimitReached ? 'Orbit limit reached for this organization' : null"
            @click="onCreateClick"
            class="create-button"
          >
            <Plus :size="14" />
            <span>New orbit</span>
          </d-button>
        </footer>
      </div>
    </Popover>
    <OrbitCreator
      v-if="organizationStore.currentOrganization"
      v-model:visible="isCreateMode"
      :organization-id="organizationStore.currentOrganization.id"
    />
    <OrbitEditor
      v-if="orbitsStore.currentOrbitDetails"
      v-model:visible="isSettingsMode"
      :orbit="orbitsStore.currentOrbitDetails"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch, inject, type Ref } from 'vue'
import { Orbit, ChevronDown, Plus, Bolt } from 'lucide-vue-next'
import { Popover } from 'primevue'
import { useOrbitsStore } from '@/stores/orbits'
import { useOrganizationStore } from '@/stores/organization'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import OrbitCreator from './creator/OrbitCreator.vue'
import UiId from '@/components/ui/UiId.vue'
import OrbitEditor from './editor/OrbitEditor.vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const activePopover = inject<Ref<string | null>>('activePopover')

const ORBIT_ROUTES = ['orbit-registry', 'orbit-deployments', 'orbit-satellites', 'orbit-secrets']
const DEEP_ROUTES = [
  'collection',
  'artifact',
  'model-card',
  'experiment-snapshot',
  'attachments',
  'compare',
  'deployment-schema',
]

const orbitsStore = useOrbitsStore()
const organizationStore = useOrganizationStore()
const isSettingsMode = ref(false)
const popover = ref()
const isCreateMode = ref(false)

function isOnOrbitRoute() {
  return ORBIT_ROUTES.includes(route.name as string)
}

const isOrbitLimitReached = computed(() => {
  const details = organizationStore.organizationDetails
  if (!details) return true
  return details.total_orbits >= details.orbits_limit
})

const createAvailable = computed(
  () =>
    organizationStore.currentOrganization?.permissions?.orbit?.includes(PermissionEnum.create) ??
    false,
)

function toggle(event: any) {
  const isMobile = window.innerWidth <= 768
  if (isMobile && !popover.value?.visible && activePopover) {
    activePopover.value = 'orbit'
  }
  popover.value.toggle(event)
}

if (activePopover) {
  watch(activePopover, (val) => {
    const isMobile = window.innerWidth <= 768
    if (isMobile && val !== 'orbit' && popover.value?.visible) {
      popover.value.hide()
    }
  })
}

async function onOrbitClick(orbitId: string) {
  const currentRouteName = route.name as string
  const orgId = organizationStore.currentOrganization?.id

  if (DEEP_ROUTES.includes(currentRouteName)) {
    await router.replace({
      name: 'orbit-registry',
      params: orgId ? { organizationId: orgId } : {},
      query: { orbitId },
    })
  } else if (isOnOrbitRoute()) {
    await router.push({ query: { ...route.query, orbitId } })
  } else {
    orbitsStore.setCurrentOrbitId(orbitId)
  }

  popover.value.hide()
}

function onSettingsClick() {
  popover.value.toggle(false)
  isSettingsMode.value = true
}

function onCreateClick() {
  popover.value.toggle(false)
  isCreateMode.value = true
}

watch(
  () => organizationStore.currentOrganization?.id,
  async (id, oldId) => {
    if (!id) {
      orbitsStore.reset()
      return
    }

    if (id === oldId && orbitsStore.orbitsList.length) return

    orbitsStore.reset()
    await orbitsStore.loadOrbitsList(id)

    try {
      await organizationStore.getOrganizationDetails(id)
    } catch (e) {
      console.warn('No permission to load organization details')
    }

    const orbitIdFromQuery = route.query.orbitId as string | undefined
    const targetOrbitId =
      orbitIdFromQuery && orbitsStore.orbitsList.some((o) => o.id === orbitIdFromQuery)
        ? orbitIdFromQuery
        : (orbitsStore.orbitsList[0]?.id ?? null)

    if (targetOrbitId) {
      orbitsStore.setCurrentOrbitId(targetOrbitId)
      if (isOnOrbitRoute() && route.query.orbitId !== targetOrbitId) {
        await router.replace({
          query: { ...route.query, orbitId: targetOrbitId },
        })
      }
    }
  },
  { immediate: true },
)
</script>

<style scoped>
.orbit-popover-wrapper {
  position: relative;
}

.menu-link {
  display: flex;
  width: 180px;
  padding: 8px 12px;
  align-items: center;
  gap: var(--menubar-item-gap, 7px);
  color: var(--p-menu-item-color);
  font-weight: 500;
  height: 32px;
  white-space: nowrap;
  font-size: 14px;
  justify-content: flex-start;
  transition:
    color 0.3s,
    background-color 0.3s;
}

.label {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
  max-width: 150px;
}

.icon {
  flex: 0 0 auto;
}

.popover-content {
  padding: 14px 6px;
}

.header {
  padding-bottom: 8px;
  border-bottom: 1px solid var(--p-divider-border-color);
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  width: 100%;
}

.header-content {
  width: 100%;
}

.name {
  margin-bottom: 4px;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 500;
}

.meta-row {
  display: flex;
  align-items: center;
}

.collections-count {
  font-weight: 300;
  color: var(--p-text-muted-color);
  font-size: 14px;
}

.id-row {
  margin-left: auto;
  font-size: 12px;
  color: var(--p-text-muted-color);
}

.popover-label {
  padding: 8px 12px;
  color: var(--p-menu-submenu-label-color);
  font-size: 14px;
  font-weight: var(--p-menu-submenu-label-font-weight);
}

.orbit-item {
  display: flex;
  gap: 4px;
}

.menu-item {
  flex: 1 1 auto;
  text-align: left;
  padding: 8px 12px;
  cursor: pointer;
  font-size: 16px;
  color: var(--p-menu-item-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  transition:
    color 0.3s,
    background-color 0.3s;
  border-radius: 4px;
}

.menu-item:hover {
  color: var(--p-menu-item-focus-color);
}

.active .menu-item {
  background-color: var(--p-menu-item-focus-background);
  color: var(--p-menu-item-focus-color);
}

.empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 16px 12px;
  color: var(--p-text-muted-color);
}

.empty-text-header {
  overflow: hidden;
  color: var(--p-text-color);
  text-overflow: ellipsis;
  font-size: 16px;
}

.empty-text {
  color: var(--p-text-muted-color);
  text-align: center;
  font-size: 12px;
  font-weight: 400;
  line-height: normal;
}

.footer {
  padding-top: 16px;
  border-top: 1px solid var(--p-divider-border-color);
  margin-top: 16px;
}

.create-button {
  width: 100%;
}

:deep(.p-popover) {
  top: calc(100% + 4px) !important;
  left: 0 !important;
  transform: none !important;
}

:deep(.p-popover) {
  top: calc(100% + 4px) !important;
  left: 0 !important;
  transform: none !important;
}
.orbit-item :deep(.p-button) {
  flex-shrink: 0;
  min-width: 32px;
}

@media (max-width: 768px) {
  :deep(.p-popover) {
    left: auto !important;
    right: 0 !important;
    max-width: calc(100vw - 32px);
  }
}
</style>
