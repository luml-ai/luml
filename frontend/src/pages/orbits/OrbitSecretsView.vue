<template>
  <div v-if="!loading" class="list">
    <SecretsList
      :organization-id="orbitsStore.currentOrbitDetails!.organization_id"
      :edit-available="canEditSecret"
      :copy-available="canReadSecret"
    />
  </div>

  <SecretCreator
    v-if="canCreateSecret"
    :organization-id="orbitsStore.currentOrbitDetails!.organization_id"
    :orbit-id="orbitsStore.currentOrbitDetails!.id"
    v-model:visible="secretsStore.creatorVisible"
    @update:visible="(val) => (val ? secretsStore.showCreator() : secretsStore.hideCreator())"
  />
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref } from 'vue'
import { useToast } from 'primevue'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useOrbitsStore } from '@/stores/orbits'
import { useSecretsStore } from '@/stores/orbit-secrets'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import SecretsList from '@/components/orbit-secrets/SecretsList.vue'
import SecretCreator from '@/components/orbit-secrets/SecretCreator.vue'

const orbitsStore = useOrbitsStore()
const secretsStore = useSecretsStore()
const canCreateSecret = computed(
  () => !!orbitsStore.getCurrentOrbitPermissions?.orbit_secret?.includes(PermissionEnum.create),
)
const canEditSecret = computed(
  () => !!orbitsStore.getCurrentOrbitPermissions?.orbit_secret?.includes(PermissionEnum.update),
)
const canReadSecret = computed(
  () => !!orbitsStore.getCurrentOrbitPermissions?.orbit_secret?.includes(PermissionEnum.read),
)
const toast = useToast()

const loading = ref(false)

onBeforeMount(async () => {
  try {
    loading.value = true
    const currentOrbit = orbitsStore.currentOrbitDetails
    if (currentOrbit?.organization_id && currentOrbit?.id) {
      await secretsStore.loadSecrets(currentOrbit.organization_id, currentOrbit.id)
    }
  } catch {
    toast.add(simpleErrorToast('Failed to load secrets'))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
