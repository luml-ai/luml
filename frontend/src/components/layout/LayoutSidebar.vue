<template>
  <aside id="sidebar" class="sidebar" :class="{ closed: !isSidebarOpened }">
    <div>
      <div class="organization-button-wrapper">
        <OrganizationManagePopover v-if="authStore.isAuth"></OrganizationManagePopover>
        <d-button
          v-else
          disabled
          variant="text"
          class="menu-link disabled"
          v-tooltip.right="'Log in to unlock this feature.'"
        >
          <Users :size="14" class="icon"></Users>
          <span class="label">My Org...</span>
          <ChevronDown :size="20" class="icon" />
        </d-button>
      </div>
      <nav class="nav">
        <ul class="list">
          <li v-for="item in SIDEBAR_MENU" :key="item.id" class="item">
            <div
              v-if="item.disabled"
              v-tooltip.bottom="isSidebarOpened ? item.tooltipMessage : null"
              v-tooltip.right="!isSidebarOpened ? item.tooltipMessage : null"
              class="menu-link disabled"
            >
              <component :is="item.icon" :size="14" class="icon"></component>
              <span>{{ item.label }}</span>
            </div>

            <div
              v-else-if="item.authRequired && !authStore.isAuth"
              v-tooltip.right="'Log in to unlock this feature.'"
              class="menu-link disabled"
            >
              <component :is="item.icon" :size="14" class="icon"></component>
              <span>{{ item.label }}</span>
            </div>
            <div
              v-else-if="requiresOrgId(item.route) && !organizationsStore.currentOrganization?.id"
              class="menu-link disabled"
              v-tooltip.right="'Please select an organization'"
            >
              <component :is="item.icon" :size="14" class="icon"></component>
              <span>{{ item.label }}</span>
            </div>

            <router-link
              v-else
              :to="getRouteParams(item.route)"
              class="menu-link"
              @click="sendAnalytics(item.analyticsOption)"
            >
              <component :is="item.icon" :size="14" class="icon"></component>
              <span>{{ item.label }}</span>
            </router-link>
          </li>
        </ul>
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
import { ArrowLeftToLine, ChevronDown, Users, Github, Star } from 'lucide-vue-next'
import { computed, onBeforeMount, onMounted, ref, watch } from 'vue'
import { SIDEBAR_MENU, SIDEBAR_MENU_BOTTOM } from '@/constants/constants'
import { AnalyticsService, AnalyticsTrackKeysEnum } from '@/lib/analytics/AnalyticsService'
import { useWindowSize } from '@/hooks/useWindowSize'
import OrganizationManagePopover from '../organizations/OrganizationManagePopover.vue'
import { useAuthStore } from '@/stores/auth'
import { useOrganizationStore } from '@/stores/organization'
import { GitHubService } from '@/lib/github/GitHubService'

const { width } = useWindowSize()
const authStore = useAuthStore()
const organizationsStore = useOrganizationStore()

const isSidebarOpened = ref(true)
const githubStarsCount = ref(null)
const ROUTES_REQUIRING_ORG_ID = ['orbits', 'orbit', 'organization', 'collection']

const getFormattedGithubStars = computed(() => {
  if (githubStarsCount.value === null) return null
  else if (githubStarsCount.value < 1000) return githubStarsCount.value
  else return (githubStarsCount.value / 1000).toFixed() + 'K'
})

function requiresOrgId(routeName: string): boolean {
  return ROUTES_REQUIRING_ORG_ID.includes(routeName)
}

function getRouteParams(routeName: string) {
  const baseRoute = { name: routeName }
  if (!requiresOrgId(routeName)) {
    return baseRoute
  }

  const orgId = organizationsStore.currentOrganization?.id
  if (!orgId) {
    console.warn(`Route "${routeName}" requires organizationId but none is selected`)
    return baseRoute
  }
  if (routeName === 'orbits') {
    return {
      ...baseRoute,
      params: { organizationId: orgId },
    }
  }

  if (routeName === 'organization') {
    return {
      ...baseRoute,
      params: { id: orgId },
    }
  }
  return {
    ...baseRoute,
    params: { organizationId: orgId },
  }
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
  padding: 96px 16px 16px;
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

.menu-link.router-link-active {
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

.menu-link.router-link-active .icon {
  color: var(--p-menu-item-icon-focus-color);
}

.closed .menu-link {
  width: 30px;
}

[data-theme='dark'] .router-link-active {
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

  .menu-link.router-link-active:hover {
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

  [data-theme='dark'] .menu-link.router-link-active {
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
