<template>
  <div>
    <div class="toolbar">
      <h3 class="label">
        List of Orbits for current organization ({{
          organizationStore.organizationDetails?.orbits.length || 0
        }})
      </h3>
      <Button v-if="createAvailable" @click="showCreator = true">
        <Plus :size="14" />
        <span>New Orbit</span>
      </Button>
    </div>
    <div class="users-wrapper">
      <div class="users">
        <div class="users-header">
          <div class="row">
            <div class="cell">Orbit</div>
            <div class="cell">Number of members</div>
            <div class="cell">Created</div>
            <div class="cell"></div>
          </div>
        </div>
        <div v-if="organizationStore.organizationDetails?.orbits.length" class="users-list">
          <div v-for="orbit in organizationStore.organizationDetails.orbits" class="row">
            <div class="cell cell-user" style="overflow: hidden">
              <div>
                <h4 style="overflow: hidden; text-overflow: ellipsis">{{ orbit.name }}</h4>
              </div>
            </div>
            <div class="cell">{{ orbit.total_members }}</div>
            <div class="cell">{{ new Date(orbit.created_at).toLocaleDateString() }}</div>
            <div class="cell">
              <OrganizationOrbitSettings :orbit-id="orbit.id"></OrganizationOrbitSettings>
            </div>
          </div>
        </div>
        <div v-else>
          All Orbits linked to this organization will be shown in this table once available.
        </div>
      </div>
    </div>
    <OrbitCreator
      v-if="organizationStore.currentOrganization"
      v-model:visible="showCreator"
      :organization-id="organizationStore.currentOrganization.id"
    ></OrbitCreator>
  </div>
</template>

<script setup lang="ts">
import { useOrganizationStore } from '@/stores/organization'
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { computed, ref } from 'vue'
import OrganizationOrbitSettings from './OrganizationOrbitSettings.vue'
import OrbitCreator from '../orbits/creator/OrbitCreator.vue'

const organizationStore = useOrganizationStore()

const showCreator = ref(false)

const createAvailable = computed(() => {
  return !!organizationStore.currentOrganization?.permissions?.orbit?.includes(
    PermissionEnum.create,
  )
})
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
  min-width: 650px;
}
.users-header {
  padding: 10px 0;
  font-weight: 500;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--p-divider-border-color);
}
.row {
  display: grid;
  grid-template-columns: 1fr 180px 120px 35px;
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
</style>
