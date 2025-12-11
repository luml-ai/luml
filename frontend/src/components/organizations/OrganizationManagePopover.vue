<template>
  <div>
    <d-button variant="text" class="menu-link" @click="toggle">
      <Users :size="14" class="icon"></Users>
      <span class="label">{{ organizationStore.currentOrganization?.name }}</span>
      <ChevronDown :size="20" class="icon" />
    </d-button>
    <Popover ref="popover" class="popover-without-arrow" style="width: 330px">
      <div class="popover-content">
        <header class="header">
          <Avatar size="large" :label="currentOrganizationAvatarLabel" />
          <div class="header-content">
            <div class="name">{{ organizationStore.currentOrganization?.name }}</div>
            <div class="members-row">
              <div class="members">
                {{ organizationStore.currentOrganization?.members_count }} member
              </div>
              <div class="id-row" v-if="organizationStore.currentOrganization?.id">
                <UiId :id="organizationStore.currentOrganization.id" class="id-value"></UiId>
              </div>
            </div>
          </div>
        </header>
        <div class="popover-label">Switch to Organization</div>
        <div
          v-for="organization in organizationStore.availableOrganizations"
          class="organization"
          :class="{ active: organization.id === organizationStore.currentOrganization?.id }"
        >
          <button class="menu-item" @click="onOrganizationClick(organization.id)">
            {{ organization.name }}
          </button>
          <OrganizationLeavePopover
            v-if="
              organization.id !== organizationStore.currentOrganization?.id &&
              organization.permissions.organization.includes(PermissionEnum.leave)
            "
            :organizationId="organization.id"
          ></OrganizationLeavePopover>
        </div>
        <footer class="footer">
          <d-button severity="secondary" @click="onCreateClick">
            <Plus :size="14" />
            <span>Create new</span>
          </d-button>
          <d-button
            v-if="organizationStore.currentOrganization"
            asChild
            variant="outlined"
            severity="secondary"
            :disabled="isSettingsDisabled"
            v-slot="slotProps"
          >
            <button v-if="isSettingsDisabled" :class="slotProps.class" disabled>
              <Bolt :size="14" />
              <span>Settings</span>
            </button>
            <router-link
              v-else
              :to="{
                name: 'organization-members',
                params: { id: organizationStore.currentOrganization.id },
              }"
              :class="slotProps.class"
              @click="toggle"
            >
              <Bolt :size="14" />
              <span>Settings</span>
            </router-link>
          </d-button>
        </footer>
      </div>
    </Popover>
    <Dialog v-model:visible="isCreateMode" modal :draggable="false" style="max-width: 500px">
      <template #header>
        <h2 class="creator-title">Create a new Organization</h2>
      </template>
      <div>
        <p class="creator-text">
          Use organizations to manage people, permissions, and multiple orbits in one place.
        </p>
        <OrganizationCreator @close="isCreateMode = false"></OrganizationCreator>
      </div>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { Users, ChevronDown, Plus, Bolt } from 'lucide-vue-next'
import { Popover, Avatar, Dialog } from 'primevue'
import { useOrganizationStore } from '@/stores/organization'
import OrganizationCreator from './OrganizationCreator.vue'
import OrganizationLeavePopover from './OrganizationLeavePopover.vue'
import UiId from '../ui/UiId.vue'
import { PermissionEnum } from '@/lib/api/api.interfaces'

const organizationStore = useOrganizationStore()

const popover = ref()
const isCreateMode = ref(false)

const isSettingsDisabled = computed(
  () =>
    !organizationStore.currentOrganization?.permissions.organization.includes(PermissionEnum.read),
)
const currentOrganizationAvatarLabel = computed(() =>
  organizationStore.currentOrganization?.name.charAt(0).toUpperCase(),
)

function toggle(event: any) {
  popover.value.toggle(event)
}

function onCreateClick() {
  popover.value.toggle(false)
  isCreateMode.value = true
}

async function onOrganizationClick(organizationId: string) {
  await organizationStore.setCurrentOrganizationId(organizationId)
}
</script>

<style scoped>
.menu-link {
  width: 100%;
  padding: 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--p-menu-item-color);
  text-decoration: none;
  font-weight: 500;
  height: 32px;
  white-space: nowrap;
  overflow: hidden;
  width: 100%;
  font-size: 14px;
  justify-content: flex-start;
  transition:
    color 0.3s,
    background-color 0.3s,
    width 0.3s;
}

.label {
  flex: 1 1 auto;
  overflow: hidden;
  text-overflow: ellipsis;
  text-align: left;
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
  width: calc(100% - 50px);
}
.avatar {
  border-radius: 6px;
  flex: 0 0 auto;
  overflow: hidden;
}
.name {
  margin-bottom: 4px;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
}
.members-row {
  display: flex;
}
.members {
  font-weight: 300;
  color: var(--p-text-muted-color);
  font-size: 14px;
}
.id-row {
  margin-left: auto;
  color: var(--p-text-muted-color);
}

.popover-label {
  padding: 8px 12px;
  color: var(--p-menu-submenu-label-color);
  font-size: 14px;
  font-weight: var(--p-menu-submenu-label-font-weight);
}

.organization {
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

.footer {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  padding-top: 16px;
  border-top: 1px solid var(--p-divider-border-color);
  margin-top: 16px;
}

.creator-title {
  font-weight: 600;
  font-size: 20px;
  text-transform: uppercase;
}

.creator-text {
  color: var(--p-text-muted-color);
  margin-bottom: 28px;
}
</style>
