<template>
  <div v-if="loading" class="loading-container">
    <Skeleton v-for="i in 10" :key="i" style="height: 146.5px" />
  </div>
  <div v-else>
    <div v-if="!collectionsStore.collectionsList.length" class="content">
      <Folders :size="35" color="var(--p-primary-color)" />
      <h3 class="label">Welcome to the Registry</h3>
      <div class="text">
        <p>
          Organize your best model checkpoints into collections for easy access, versioning, and
          collaboration.
        </p>
        <p>Start by creating your first collection.</p>
      </div>
    </div>
    <CollectionsList
      v-else
      :edit-available="
        !!orbitsStore.getCurrentOrbitPermissions?.collection.includes(PermissionEnum.update)
      "
    ></CollectionsList>
  </div>
  <CollectionCreator
    :organization-id="orbitsStore.currentOrbitDetails!.organization_id"
    :orbit-id="orbitsStore.currentOrbitDetails!.id"
    :visible="collectionsStore.creatorVisible"
    @update:visible="updateCreatorVisible"
  />
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted, ref } from 'vue'
import { Skeleton, useToast } from 'primevue'
import { Folders } from 'lucide-vue-next'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useCollectionsStore } from '@/stores/collections'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'
import CollectionsList from '@/components/orbits/tabs/registry/CollectionsList.vue'
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue'

const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()

const loading = ref(false)

function updateCreatorVisible(visible: boolean | undefined) {
  visible ? collectionsStore.showCreator() : collectionsStore.hideCreator()
}

onBeforeMount(async () => {
  try {
    loading.value = true
    await collectionsStore.loadCollections()
  } catch (e) {
    toast.add(simpleErrorToast('Failed to load collections'))
  } finally {
    loading.value = false
  }
})

onUnmounted(() => {
  collectionsStore.reset()
})
</script>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  gap: 8px;
  min-height: 150px;
  border-radius: 8px;
  box-shadow: var(--card-shadow);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
}
.label {
  font-weight: 500;
}
.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
.loading-container {
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
