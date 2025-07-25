<template>
  <div v-if="!loading">
    <header class="header">
      <h2 class="title">{{ orbitsStore.currentOrbitDetails?.name }}</h2>
      <Button
        v-if="orbitsStore.getCurrentOrbitPermissions?.collection.includes(PermissionEnum.create)"
        class="button"
        @click="showCreator = true"
      >
        <Plus :size="14" />
        <span>Create collection</span>
      </Button>
    </header>
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
  <CollectionCreator v-model:visible="showCreator"></CollectionCreator>
</template>

<script setup lang="ts">
import { onBeforeMount, onUnmounted, ref } from 'vue'
import { Button, useToast } from 'primevue'
import { Plus, Folders } from 'lucide-vue-next'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useCollectionsStore } from '@/stores/collections'
import CollectionsList from '@/components/orbits/tabs/registry/CollectionsList.vue'
import CollectionCreator from '@/components/orbits/tabs/registry/CollectionCreator.vue'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'

const orbitsStore = useOrbitsStore()
const collectionsStore = useCollectionsStore()
const toast = useToast()

const showCreator = ref(false)
const loading = ref(false)

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
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 40px;
  margin-bottom: 20px;
}
.button {
  flex: 0 0 auto;
}
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
  background-color: var(--p-content-background);
}
.label {
  font-weight: 500;
}
.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
