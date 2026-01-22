<template>
  <Breadcrumb :model="breadcrumbs" :pt="{ root: { style: 'padding-left: 0' } }">
    <template #item="{ item, props }">
      <RouterLink v-if="item.route" v-slot="{ href, navigate }" :to="item.route" custom>
        <a :href="href" v-bind="props.action" @click="navigate">
          {{ item.label }}
        </a>
      </RouterLink>
    </template>
  </Breadcrumb>
</template>

<script setup lang="ts">
import type { MenuItem } from 'primevue/menuitem'
import { Breadcrumb } from 'primevue'
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useCollectionsStore } from '@/stores/collections'
import { useModelsStore } from '@/stores/models'

const route = useRoute()
const collectionStore = useCollectionsStore()
const modelsStore = useModelsStore()

const breadcrumbs = computed<(MenuItem & { route: string })[]>(() => {
  const list = [
    {
      label: 'Registry',
      route: `/organization/${route.params.organizationId}/orbit/${route.params.id}`,
    },
  ]
  if (collectionStore.currentCollection) {
    list.push({
      label: collectionStore.currentCollection.name,
      route: `/organization/${route.params.organizationId}/orbit/${route.params.id}/collection/${route.params.collectionId}`,
    })
  }
  if (modelsStore.currentModel) {
    list.push({
      label: modelsStore.currentModel.model_name,
      route: `/organization/${route.params.organizationId}/orbit/${route.params.id}/collection/${route.params.collectionId}/models/${route.params.modelId}`,
    })
  }
  const modelsToCompare = typeof route.query.models === 'object' ? route.query.models : null
  if (modelsToCompare?.length) {
    const queryString = modelsToCompare.map((id) => `models=${id}`).join('&')
    list.push({
      label: `Multi-model comparison (${modelsToCompare.length})`,
      route: `/organization/${route.params.organizationId}/orbit/${route.params.id}/collection/${route.params.collectionId}/compare?${queryString}`,
    })
  }

  return list
})
</script>

<style scoped></style>
