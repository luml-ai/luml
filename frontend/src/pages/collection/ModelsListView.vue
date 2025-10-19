<template>
  <div>
    <CollectionHeader
      v-if="collectionsStore.currentCollection"
      :id="collectionsStore.currentCollection.id"
      :title="collectionsStore.currentCollection.name"
      :add-available="
        !!orbitsStore.getCurrentOrbitPermissions?.model.includes(PermissionEnum.create)
      "
      @add="modelCreatorVisible = true"
    ></CollectionHeader>
    <CollectionModelsTable class="table"></CollectionModelsTable>
    <CollectionModelCreator v-model:visible="modelCreatorVisible"></CollectionModelCreator>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { PermissionEnum } from '@/lib/api/DataforceApi.interfaces'
import { useCollectionsStore } from '@/stores/collections'
import { useOrbitsStore } from '@/stores/orbits'
import CollectionHeader from '@/components/orbits/tabs/registry/collection/CollectionHeader.vue'
import CollectionModelsTable from '@/components/orbits/tabs/registry/collection/CollectionModelsTable.vue'
import CollectionModelCreator from '@/components/orbits/tabs/registry/collection/model/CollectionModelCreator.vue'

const collectionsStore = useCollectionsStore()
const orbitsStore = useOrbitsStore()

const modelCreatorVisible = ref(false)
</script>

<style scoped></style>
