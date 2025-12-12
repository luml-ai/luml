<template>
  <div>
    <h3 class="label">Members ({{ members.length }})</h3>
    <div class="toolbar">
      <div class="buttons">
        <OrganizationCreateInvite></OrganizationCreateInvite>
        <OrganizationInviteManager></OrganizationInviteManager>
      </div>
      <div class="list">
        <div class="item">
          <div class="item-label">Owner</div>
          <Badge :value="ownersCount" />
        </div>
        <div class="item">
          <div class="item-label">Admin</div>
          <Badge :value="adminsCount" />
        </div>
        <div class="item">
          <div class="item-label">Member</div>
          <Badge :value="membersCount" />
        </div>
      </div>
    </div>
    <div class="users-wrapper">
      <div class="users">
        <div class="users-header">
          <div class="row">
            <div class="cell">User</div>
            <div class="cell">Role</div>
            <div class="cell">Date added</div>
            <div class="cell"></div>
          </div>
        </div>
        <div class="users-list">
          <div v-for="member in members" class="row">
            <div class="cell cell-user">
              <Avatar
                :label="member.user.photo ? undefined : member.user.full_name[0]"
                shape="circle"
                :image="member.user.photo"
              />
              <div>
                <h4>{{ member.user.full_name }}</h4>
                <div class="email">{{ member.user.email }}</div>
              </div>
            </div>
            <div class="cell">{{ member.role }}</div>
            <div class="cell">{{ new Date(member.created_at).toLocaleDateString() }}</div>
            <div class="cell">
              <OrganizationUserSettings
                v-if="
                  member.role === OrganizationRoleEnum.member ||
                  (member.role === OrganizationRoleEnum.admin && isUserOwner)
                "
                :member="member"
              ></OrganizationUserSettings>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Badge, Avatar } from 'primevue'
import { useOrganizationStore } from '@/stores/organization'
import { computed } from 'vue'
import { OrganizationRoleEnum } from './organization.interfaces'
import OrganizationUserSettings from './OrganizationUserSettings.vue'
import OrganizationCreateInvite from './OrganizationCreateInvite.vue'
import OrganizationInviteManager from './OrganizationInviteManager.vue'
import { useUserStore } from '@/stores/user'

const organizationStore = useOrganizationStore()
const userStore = useUserStore()

const members = computed(() => organizationStore.organizationDetails?.members || [])
const ownersCount = computed(
  () => members.value.filter((member) => member.role === OrganizationRoleEnum.owner).length,
)
const adminsCount = computed(
  () => members.value.filter((member) => member.role === OrganizationRoleEnum.admin).length,
)
const membersCount = computed(
  () => members.value.filter((member) => member.role === OrganizationRoleEnum.member).length,
)
const isUserOwner = computed(
  () =>
    members.value.find((member) => member.user.id === userStore.getUserId)?.role ===
    OrganizationRoleEnum.owner,
)
</script>

<style scoped>
.label {
  font-size: 20px;
  font-weight: 500;
  margin-bottom: 12px;
}
.toolbar {
  display: flex;
  justify-content: space-between;
  gap: 50px;
  align-items: center;
  margin-bottom: 12px;
}
.buttons {
  display: flex;
  gap: 12px;
}

.list {
  display: flex;
  gap: 24px;
  align-items: center;
}
.item {
  display: inline-flex;
  gap: 7.5px;
  align-items: center;
}
.item-label {
  font-weight: 500;
}
.users-wrapper {
  overflow-x: auto;
  padding: 16px;
  border-radius: 8px;
  background: var(--p-card-background);
  border: 1px solid var(--p-content-border-color);
  box-shadow: var(--card-shadow);
}
.users {
  min-width: 600px;
}
.users-header {
  padding: 10px 0;
  font-weight: 500;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--p-divider-border-color);
}
.row {
  display: grid;
  grid-template-columns: 1fr 100px 100px 35px;
  align-items: center;
  gap: 40px;
}
.cell-user {
  display: flex;
  gap: 8px;
  align-items: center;
}
.email {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
.users-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

@media (max-width: 992px) {
  .buttons {
    flex-direction: column;
  }
  .list {
    flex-direction: column;
    align-items: flex-end;
    gap: 8px;
  }
}
</style>
