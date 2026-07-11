<template>
  <div>
    <CollectionHeader
      v-if="collectionsStore.currentCollection"
      :id="collectionsStore.currentCollection.id"
      :title="collectionsStore.currentCollection.name"
      :add-available="
        !!orbitsStore.getCurrentOrbitPermissions?.artifact.includes(PermissionEnum.create)
      "
      @add="creatorVisible = true"
    ></CollectionHeader>
    <ArtifactsTable class="table"></ArtifactsTable>
    <ArtifactCreator v-model:visible="creatorVisible"></ArtifactCreator>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { useCollectionsStore } from '@/stores/collections'
import { useOrbitsStore } from '@/stores/orbits'
import CollectionHeader from '@/components/orbits/tabs/registry/collection/CollectionHeader.vue'
import ArtifactsTable from '@/components/orbits/tabs/registry/collection/artifacts-table/ArtifactsTable.vue'
import ArtifactCreator from '@/components/orbits/tabs/registry/collection/artifact/ArtifactCreator.vue'

const collectionsStore = useCollectionsStore()
const orbitsStore = useOrbitsStore()

const creatorVisible = ref(false)
</script>

<style scoped></style>
