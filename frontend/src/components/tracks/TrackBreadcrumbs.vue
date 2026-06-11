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
import type { TrackBreadcrumbsProps } from './tracks.interface'
import { computed } from 'vue'
import { Breadcrumb } from 'primevue'
import { useRoute } from 'vue-router'

const props = defineProps<TrackBreadcrumbsProps>()

const route = useRoute()

const breadcrumbs = computed(() => [
  {
    label: 'Registry',
    route: {
      name: 'orbit-tracks',
      params: { organizationId: route.params.organizationId, id: route.params.id },
    },
  },
  { label: props.trackName, route: { name: 'track', params: { id: props.trackId } } },
])
</script>

<style scoped></style>
