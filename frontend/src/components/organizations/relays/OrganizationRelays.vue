<template>
  <div v-if="organizationId">
    <div class="header">
      <h3 class="label">
        List of Relays for current organization ({{ relaysStore.relays.length }})
      </h3>
      <RelayCreator v-if="canCreate" :organization-id="organizationId" />
    </div>
    <OrganizationRelaysTable :organization-id="organizationId" :can-manage="canUpdate" />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import { useRelaysStore } from '@/stores/relays'
import OrganizationRelaysTable from './OrganizationRelaysTable.vue'
import RelayCreator from './RelayCreator.vue'

const organizationStore = useOrganizationStore()
const relaysStore = useRelaysStore()

const organizationId = computed(() => organizationStore.currentOrganization?.id)
const relayPermissions = computed(
  () => organizationStore.currentOrganization?.permissions?.relay ?? [],
)
const canCreate = computed(() => relayPermissions.value.includes(PermissionEnum.create))
const canUpdate = computed(() => relayPermissions.value.includes(PermissionEnum.update))
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.label {
  font-weight: 500;
  font-size: 20px;
}
</style>
