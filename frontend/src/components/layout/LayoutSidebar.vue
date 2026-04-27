<template>
  <aside
    id="sidebar"
    class="sidebar"
    :class="{ closed: !isSidebarOpened }"
    :style="{ paddingTop: headerSizes.height + 32 + 'px' }"
  >
    <div>
      <nav class="nav">
        <div v-for="section in SIDEBAR_SECTIONS" :key="section.id" class="section">
          <div class="section-label">{{ section.label }}</div>
          <div class="section-divider" aria-hidden="true" />
          <ul class="list">
            <li v-for="item in section.items" :key="item.id" class="item">
              <div
                v-if="item.disabled"
                v-tooltip.bottom="isSidebarOpened ? item.tooltipMessage : null"
                v-tooltip.right="!isSidebarOpened ? item.tooltipMessage : null"
                class="menu-link disabled"
              >
                <component :is="item.icon" :size="14" class="icon" />
                <span>{{ item.label }}</span>
              </div>

              <router-link
                v-else-if="getRouteParams(item.route)"
                :to="getRouteParams(item.route)!"
                class="menu-link"
                :class="{ active: isActive(item.route) }"
                @click="sendAnalytics(item.analyticsOption)"
              >
                <component :is="item.icon" :size="14" class="icon" />
                <span>{{ item.label }}</span>
              </router-link>

              <router-link
                v-else
                :to="{ name: item.route }"
                class="menu-link"
                :class="{ active: isActive(item.route) }"
                @click="sendAnalytics(item.analyticsOption)"
              >
                <component :is="item.icon" :size="14" class="icon" />
                <span>{{ item.label }}</span>
              </router-link>
            </li>
          </ul>
        </div>
      </nav>
    </div>
    <div class="sidebar-bottom">
      <nav class="nav-bottom">
        <ul class="list">
          <li v-for="item in SIDEBAR_MENU_BOTTOM" :key="item.id" class="item">
            <a v-if="item.link" :href="item.link" target="_blank" class="menu-link">
              <component :is="item.icon" :size="14" class="icon"></component>
              <span>{{ item.label }}</span>
            </a>
          </li>
          <li class="item">
            <a
              href="https://github.com/Dataforce-Solutions/dataforce.studio"
              target="_blank"
              class="menu-link menu-link--github"
            >
              <Github :size="14" class="icon"></Github>
              <span class="menu-link__text">GitHub</span>
              <div v-if="getFormattedGithubStars !== null" class="menu-link__info">
                <Star :size="10" />
                <span>{{ getFormattedGithubStars }}</span>
              </div>
            </a>
          </li>
        </ul>
      </nav>
      <d-button
        severity="contrast"
        variant="text"
        rounded
        class="toggle-width-button"
        :class="{ closed: !isSidebarOpened }"
        @click="toggleSidebar"
      >
        <template #icon>
          <arrow-left-to-line :size="14" color="var(--p-button-text-plain-color)" />
        </template>
      </d-button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { ArrowLeftToLine, Github, Star } from 'lucide-vue-next'
import { computed, onBeforeMount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { SIDEBAR_SECTIONS, SIDEBAR_MENU_BOTTOM } from '@/constants/constants'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'
import { useWindowSize } from '@/hooks/useWindowSize'
import { useOrganizationStore } from '@/stores/organization'
import { GitHubService } from '@/lib/github/GitHubService'
import { useLayout } from '@/hooks/useLayout'
import { useOrbitsStore } from '@/stores/orbits'
import { TAB_TO_ROUTE, ROUTE_TO_TAB } from '@/constants/orbit-navigation'

const route = useRoute()
const orbitsStore = useOrbitsStore()
const { headerSizes } = useLayout()
const { width } = useWindowSize()
const organizationsStore = useOrganizationStore()

const isSidebarOpened = ref(true)
const githubStarsCount = ref(null)

const ROUTES_REQUIRING_ORG_ID = ['organization', 'collection']
const ORBIT_ROUTES = Object.values(TAB_TO_ROUTE)
const DEPLOYMENTS_GROUP = ['orbit-deployments', 'orbit-secrets']

const getFormattedGithubStars = computed(() => {
  if (githubStarsCount.value === null) return null
  else if (githubStarsCount.value < 1000) return githubStarsCount.value
  else return (githubStarsCount.value / 1000).toFixed() + 'K'
})

function isActive(routeName: string): boolean {
  const currentRouteName = route.name as string
  if (currentRouteName === 'setup') {
    const tab = (route.query.tab as string) ?? 'registry'
    return TAB_TO_ROUTE[tab] === routeName
  }
  if (routeName === 'orbit-deployments') {
    return DEPLOYMENTS_GROUP.includes(currentRouteName)
  }
  return currentRouteName === routeName
}

function requiresOrgId(routeName: string): boolean {
  return ROUTES_REQUIRING_ORG_ID.includes(routeName)
}

function getRouteParams(routeName: string) {
  if (ORBIT_ROUTES.includes(routeName)) {
    const orgId = organizationsStore.currentOrganization?.id
    const orbitId = orbitsStore.currentOrbitId
    if (orgId && orbitId) {
      return {
        name: routeName,
        params: { organizationId: orgId, id: orbitId },
      }
    }
    return {
      name: 'setup',
      query: { tab: ROUTE_TO_TAB[routeName] },
    }
  }

  if (requiresOrgId(routeName)) {
    const orgId = organizationsStore.currentOrganization?.id
    if (!orgId) return null
    if (routeName === 'organization') return { name: routeName, params: { id: orgId } }
    return { name: routeName, params: { organizationId: orgId } }
  }

  return null
}

const toggleSidebar = () => {
  isSidebarOpened.value = !isSidebarOpened.value
}

function windowResizeHandler() {
  if (window.innerWidth < 992 && isSidebarOpened.value === true) {
    isSidebarOpened.value = false
  }
}

function sendAnalytics(option: string) {
  AnalyticsService.track(AnalyticsTrackKeysEnum.side_menu_select, { option })
}

async function getGithubStarsCount() {
  try {
    githubStarsCount.value = await GitHubService.getStarsCount()
  } catch (e) {
    console.error(e)
  }
}

watch(width, () => {
  windowResizeHandler()
})

onBeforeMount(() => {
  getGithubStarsCount()
})

onMounted(() => {
  windowResizeHandler()
})
</script>

<style scoped>
.sidebar {
  padding: 0 16px 16px;
  background-color: var(--p-content-background);
  border-right: 1px solid var(--p-divider-border-color);
  width: 180px;
  position: relative;
  transition: width 0.3s;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.sidebar.closed {
  width: 67px;
}

.organization-button-wrapper {
  margin-bottom: 8px;
}

.sidebar-bottom {
  display: flex;
  flex-direction: column;
}

.nav-bottom {
  padding-bottom: 8px;
  border-bottom: 1px solid var(--p-divider-border-color);
  margin-bottom: 4px;
}

.section + .section {
  margin-top: 20px;
}

.section-label {
  padding: 0 8px 8px;
  font-size: 12px;
  font-weight: 500;
  color: var(--p-text-muted-color);
  opacity: 0.7;
}

.section-divider {
  display: none;
  height: 1px;
  background: var(--p-divider-border-color);
  margin: 0 8px 12px;
}

.closed .section-label {
  display: none;
}

.closed .section + .section .section-divider {
  display: block;
}

.list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.menu-link {
  padding: 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 8px;
  color: var(--p-menu-item-color);
  text-decoration: none;
  font-weight: 500;
  height: 32px;
  white-space: nowrap;
  overflow: hidden;
  width: 100%;
  font-size: 14px;
  transition:
    color 0.3s,
    background-color 0.3s,
    width 0.3s;
}

.menu-link.disabled,
.menu-link.disabled .icon {
  color: var(--p-surface-400);
}

.menu-link.active {
  background-color: var(--p-surface-0);
  color: var(--p-menu-item-focus-color);
  box-shadow: var(--card-shadow);
}

.menu-link--github {
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: 0 1px 2px 0 rgba(18, 18, 23, 0.05);
}

.menu-link__text {
  flex: 1 1 auto;
}

.menu-link__info {
  display: flex;
  align-items: center;
  gap: 2px;
  color: var(--p-text-muted-color);
  font-size: 10px;
}

.icon {
  color: var(--p-menu-item-icon-color);
  flex: 0 0 auto;
  transition: color 0.3s;
}

.label {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
}

.menu-link.active .icon {
  color: var(--p-menu-item-icon-focus-color);
}

.closed .menu-link {
  width: 30px;
}

[data-theme='dark'] .active {
  background-color: var(--p-surface-900);
  color: #fff;
  box-shadow: var(--card-shadow);
}

.toggle-width-button {
  align-self: flex-end;
  transition: transform 0.3s;
}

.toggle-width-button.closed {
  transform: rotate(180deg);
}

@media (any-hover: hover) {
  .menu-link:hover {
    background-color: var(--p-menu-item-focus-background);
    color: var(--p-menu-item-focus-color);
  }

  .menu-link.active:hover {
    background-color: var(--p-surface-0);
  }

  .menu-link:hover .icon {
    color: var(--p-menu-item-icon-focus-color);
  }

  .disabled:hover {
    background-color: transparent;
    color: var(--p-surface-400);
    box-shadow: none;
    cursor: default;
  }

  .disabled:hover .icon {
    color: var(--p-surface-400);
  }

  [data-theme='dark'] .menu-link.active {
    background-color: var(--p-surface-900);
  }
}

@media (max-width: 768px) {
  .sidebar {
    width: 100% !important;
  }
  .list {
    align-items: center;
  }
  .menu-link {
    width: auto !important;
  }
  .toggle-width-button {
    display: none;
  }
  .organization-button-wrapper {
    max-width: 200px;
    margin: 0 auto 8px;
  }
}
</style>
